"""混合检索：BM25 关键词检索（Postgres tsvector）+ 向量语义检索 + RRF 融合

面试点（README/CHANGELOG 可写）：
- 稠密向量（nomic-embed-text）擅长语义相似，但对专有名词/精确匹配召回弱
- BM25 稀疏检索擅长关键词精确匹配（塔罗牌名、咒语名、人名），对语义弱
- RRF（Reciprocal Rank Fusion）：score = Σ 1/(k + rank)，k=60 为标准值，
  无需归一化两种异构打分，直接融合排序
- 为什么不用 Elasticsearch：单机本地项目 Postgres 原生 tsvector 足够，
  避免引入 ES 运维复杂度（ponytail: YAGNI）

中文说明：'simple' 分词按空格/标点切分，中文连续文本不分词，
BM25 对中文连续短语召回有限——这正是向量检索兜底的原因（互补）。
"""
import logging

from sqlalchemy import text

from ..config import settings

logger = logging.getLogger(__name__)

# RRF 常数（标准值 60）
RRF_K = 60


def bm25_search(query: str, top_k: int, exclude_background: bool = True) -> list[dict]:
    """Postgres 全文搜索：ts_rank 排序取 top_k

    返回 [{"id", "document", "cmetadata", "rank"}]，rank 为 ts_rank 原始值。
    """
    from .ingest import get_engine

    # websearch_to_tsquery：支持引号短语与 OR，容错中文查询词
    tsq = "websearch_to_tsquery('simple', :q)"
    sql = f"""
        SELECT id, document, cmetadata, ts_rank(content_tsv, {tsq}) AS rank
        FROM langchain_pg_embedding
        WHERE content_tsv @@ {tsq}
        {_bg_sql(exclude_background)}
        ORDER BY rank DESC
        LIMIT :k
    """
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(sql), {"q": query, "k": top_k}
        ).mappings().all()
    return [
        {
            "id": r["id"],
            "document": r["document"],
            "cmetadata": r["cmetadata"] or {},
            "rank": float(r["rank"] or 0.0),
        }
        for r in rows
    ]


def _bg_sql(exclude_background: bool) -> str:
    """background 排除：cmetadata->>'category' != 'background'"""
    if exclude_background:
        return "AND cmetadata->>'category' IS DISTINCT FROM 'background'"
    return ""


def _rrf_score(ranks: list[int]) -> float:
    """RRF 融合分：Σ 1/(k + rank)"""
    return sum(1.0 / (RRF_K + r) for r in ranks)


def hybrid_retrieve(
    query: str,
    top_k: int,
    vector_results: list[dict],
    include_background: bool = False,
) -> list[dict]:
    """向量结果 + BM25 结果 RRF 融合，返回融合后的 top_k

    vector_results: retrieve() 的向量检索结果（dict 列表，含 id/content/filename/...）
    BM25 按 id 与向量结果对齐融合；仅在两个检索器同时命中的块
    获得多份 rank 加分（同义近义表达在两边都出现时更靠前）。
    """
    k = top_k or settings.top_k
    bm25 = bm25_search(
        query, top_k=k * 2,
        exclude_background=not include_background,
    )
    # 向量结果按当前顺序给 rank（1-based）；BM25 按 rank 倒序给 rank
    vec_rank = {item.get("id", i): i + 1 for i, item in enumerate(vector_results)}
    bm25_rank = {r["id"]: i + 1 for i, r in enumerate(bm25)}

    merged: dict[str, dict] = {}
    # 1) 向量结果：一份 RRF 分
    for item in vector_results:
        iid = item.get("id", "")
        score = _rrf_score([vec_rank.get(iid, len(vector_results) + 100)])
        merged[iid] = {**item, "_rrf": score}
    # 2) BM25 命中：重叠块加分，独有块以 BM25 rank 加入融合（union）
    for r in bm25:
        rid = r["id"]
        add = _rrf_score([bm25_rank.get(rid, len(bm25) + 100)])
        if rid in merged:
            merged[rid]["_rrf"] += add
        else:
            cm = r["cmetadata"] or {}
            merged[rid] = {
                "id": rid,
                "content": r["document"],
                "source": cm.get("source", ""),
                "filename": cm.get("filename", ""),
                "category": cm.get("category", ""),
                "type": cm.get("type", ""),
                "score": None,  # BM25 独有块无语义距离（前端显示「BM25」标签）
                "_rrf": add,
            }

    ordered = sorted(
        merged.values(), key=lambda x: x["_rrf"], reverse=True
    )[:k]
    for item in ordered:
        item.pop("_rrf", None)
    return ordered
