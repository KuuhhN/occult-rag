"""RAG 检索 — 语义搜索 top-K 文档块（方案 B：按问题类型分层检索）"""
from langchain_ollama import OllamaEmbeddings

from ..config import settings
from .ingest import create_vectorstore

# 知识层级分组（方案 B）
# 概览类问题 → 笔记层（浓缩精华）+ 精排版（新书只有精排版层，必须包含）
OVERVIEW_TYPES = ["note", "guide", "summary", "knowledge", "moc", "polished"]
# 细节类问题 → 全文层（信息全）：精排版/原文
DETAIL_TYPES = ["polished", "original"]

# 问题分类启发式关键词
_OVERVIEW_WORDS = [
    "讲了什么", "内容", "主题", "核心", "思想", "介绍", "概述", "结构",
    "主要", "是什么书", "这本书", "概括", "包括哪些", "哪些内容", "包含",
]
_DETAIL_WORDS = [
    "如何", "怎么", "步骤", "方法", "第几", "页码", "颜色", "定义",
    "区别", "具体", "多少", "什么时候", "在哪", "仪式", "咒语", "配方",
]


def classify_question(question: str) -> str:
    """按问题类型分类：overview（概览）/ detail（细节）/ general（通用）

    ponytail: 关键词启发式足够（本地问答场景）；需要更精确分类时
    可换小模型分类器，接口不变。
    """
    q = question.strip()
    if any(w in q for w in _OVERVIEW_WORDS):
        return "overview"
    if any(w in q for w in _DETAIL_WORDS):
        return "detail"
    return "general"


def _type_filter(question_type: str,
                 exclude_background: bool = True) -> dict | None:
    """按问题类型生成 metadata filter（None = 不限制，全层检索）
    默认排除 background（背景文献：荷马史诗/神谱等，检索优先级低）；
    exclude_background=False 时包含背景文献（设置页开关）"""
    base = ({"category": {"$ne": "background"}} if exclude_background else {})
    if question_type == "overview":
        return {**base, "type": {"$in": OVERVIEW_TYPES}}
    if question_type == "detail":
        return {**base, "type": {"$in": DETAIL_TYPES}}
    return base


def retrieve(query: str, top_k: int | None = None,
             question_type: str | None = None,
             include_background: bool = False) -> list[dict]:
    """根据查询检索最相关的文档块（方案 B：可按问题类型限定检索层级）

    question_type: "overview"/"detail"/"general"/None（自动分类）
    include_background: True 时包含背景文献（默认排除，设置页可开）
    分层结果不足 top_k 时自动用全量检索补齐（防误判导致检索空间收窄）
    """
    k = top_k or settings.top_k
    if question_type is None:
        question_type = classify_question(query)
    if include_background:
        f = _type_filter(question_type, exclude_background=False)
    else:
        f = _type_filter(question_type)

    vectorstore = create_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=k, filter=f)

    # 兜底：分层结果不足时用全量检索补齐（去重）
    # 注意：兜底无 filter，可能回填 background 块——这是"低优先级"语义
    # （核心内容优先，核心不足时背景文献兜底，总比无结果好）；若需绝对
    # 排除请将兜底也传 base filter
    if f is not None and len(results) < k:
        seen = {doc.page_content for doc, _ in results}
        for doc, score in vectorstore.similarity_search_with_score(query, k=k):
            if len(results) >= k:
                break
            if doc.page_content not in seen:
                results.append((doc, score))
                seen.add(doc.page_content)

    sources = []
    for doc, score in results:
        sources.append({
            "id": getattr(doc, "id", "") or doc.metadata.get("id", ""),
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "filename": doc.metadata.get("filename", ""),
            "category": doc.metadata.get("category", ""),
            "type": doc.metadata.get("type", ""),  # 知识层级：guide/summary/note/original/...
            "score": round(float(score), 4),  # 余弦距离（越小越相似）
        })

    return sources
