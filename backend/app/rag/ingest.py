"""RAG 文档入库 — 分块 → 向量化 → 存储到 pgvector"""
import os
import re
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document as LCDocument

from ..config import settings

# 连接字符串 — langchain_postgres 使用 psycopg (v3)
# 将 asyncpg 格式转为标准 postgresql 格式
_conn = settings.database_url


def get_engine():
    """SQLAlchemy engine（供混合检索等模块直接查 Postgres）"""
    from sqlalchemy import create_engine

    return create_engine(_conn)


def ensure_tsvector() -> None:
    """幂等迁移：保证 langchain_pg_embedding 有 content_tsv 列 + GIN 索引

    混合检索（BM25）依赖 tsvector；新环境/重建数据库后需执行。
    ponytail: 启动时调用一次，避免手写 migration 文件的开销。
    中文分词：'simple' 按空格/标点切分，中文连续文本不分词（BM25 中文
    召回有限是预期——向量检索兜底互补，见 hybrid.py 注释）。
    """
    from sqlalchemy import text as _text

    with get_engine().begin() as conn:
        conn.execute(_text(
            "ALTER TABLE langchain_pg_embedding "
            "ADD COLUMN IF NOT EXISTS content_tsv tsvector"
        ))
        # 仅回填为 NULL 的行（幂等：已回填的不重复扫）
        conn.execute(_text(
            "UPDATE langchain_pg_embedding "
            "SET content_tsv = to_tsvector('simple', coalesce(document, '')) "
            "WHERE content_tsv IS NULL"
        ))
        conn.execute(_text(
            "CREATE INDEX IF NOT EXISTS idx_embedding_content_tsv "
            "ON langchain_pg_embedding USING GIN(content_tsv)"
        ))
        # 增量一致性：触发器保证未来 INSERT/UPDATE document 自动同步 tsvector
        # （覆盖 ingest/import_notes 的批量写入，避免新文档 BM25 漏检）
        conn.execute(_text("""
            CREATE OR REPLACE FUNCTION sync_content_tsv() RETURNS trigger AS $$
            BEGIN
                NEW.content_tsv := to_tsvector('simple', coalesce(NEW.document, ''));
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        conn.execute(_text(
            "DROP TRIGGER IF EXISTS trg_content_tsv ON langchain_pg_embedding"
        ))
        conn.execute(_text("""
            CREATE TRIGGER trg_content_tsv
            BEFORE INSERT OR UPDATE OF document ON langchain_pg_embedding
            FOR EACH ROW EXECUTE FUNCTION sync_content_tsv()
        """))
# 移除 +psycopg / +asyncpg 驱动前缀，langchain_postgres 内部用 psycopg3
for prefix in ["+psycopg", "+asyncpg"]:
    _conn = _conn.replace(prefix, "")
CONNECTION_STRING = _conn

COLLECTION_NAME = "occult_knowledge"

# 目录 → 知识层级标签（供检索加权/来源展示）
# ponytail: 层级仅作元数据不参与检索逻辑；方案B（按层动态检索）需要时再加
TYPE_MAP = {
    "00-MOC": "moc",
    "01-知识库": "knowledge",
    "03-导读": "guide",
    "05-摘要": "summary",
    "06-笔记": "note",
}
# 不入库的目录（模板/日志/OCR测试样本不是知识内容）
SKIP_DIRS = {"99-模板", "04-日志", ".tessdata"}


def _infer_type(rel_path: Path) -> str:
    """从相对路径推导知识层级标签"""
    parts = rel_path.parts
    top = parts[0] if len(parts) > 1 else ""
    if top in TYPE_MAP:
        return TYPE_MAP[top]
    if top == "02-文献库":
        return "polished" if "精排版" in rel_path.name else "original"
    return "other"


def _is_redundant_original(md_file: Path, all_files: set[Path]) -> bool:
    """精排版优先：同书存在精排版时跳过原文（原文噪声大，精排版已清洗）
    约定：仅匹配 `书名_原文.md` 精确后缀；`书名原文.md`/`原文.md` 等
    非标准命名视为普通文件（不触发跳过），避免误删应保留的文件。
    """
    if not md_file.name.endswith("_原文.md"):
        return False
    polished = md_file.with_name(md_file.name[: -len("_原文.md")] + "_精排版.md")
    return polished in all_files


def create_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )


import threading

_vectorstore_cache: PGVector | None = None
_vectorstore_lock = threading.Lock()


def create_vectorstore() -> PGVector:
    """创建 PGVector 向量存储实例

    ponytail: 进程级单例 + 锁——LangChain PGVector 同进程重复实例化会触发
    "langchain_pg_collection already defined for this MetaData" 报错；
    并发检索（chat + alchemy 附图双查询）会同时触发初始化，必须加锁。
    升级路径：LangChain 修复后可直接去掉缓存与锁。
    """
    global _vectorstore_cache
    if _vectorstore_cache is None:
        with _vectorstore_lock:
            if _vectorstore_cache is None:  # 双重检查，防竞态
                embeddings = create_embeddings()
                _vectorstore_cache = PGVector(
                    embeddings=embeddings,
                    collection_name=COLLECTION_NAME,
                    connection=CONNECTION_STRING,
                    use_jsonb=True,
                )
    return _vectorstore_cache


def load_markdown_files(data_dir: str | Path) -> list[LCDocument]:
    """递归加载 .md 文件：打层级标签，精排版优先，跳过模板/冗余原文"""
    docs: list[LCDocument] = []
    data_path = Path(data_dir)

    all_files = set(data_path.rglob("*.md"))
    # 过滤掉 SKIP_DIRS 下的文件 + vault 根目录文件（如 HOME.md 导航页，parts 长度 1）
    all_files = {
        f for f in all_files
        if len(f.relative_to(data_path).parts) > 1
        and not any(part in SKIP_DIRS for part in f.relative_to(data_path).parts)
    }

    for md_file in sorted(all_files):
        try:
            rel_path = md_file.relative_to(data_path)
            parts = rel_path.parts

            # 精排版优先：同书有精排版时跳过原文
            if _is_redundant_original(md_file, all_files):
                continue

            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                continue

            # original 类型最小清洗：去掉 OCR 页码标记（## 第X页）降噪
            # ponytail: 仅去页码标记；完整清洗（页眉/元数据）用 format_ocr 生成精排版后自然接管
            if md_file.name.endswith("_原文.md"):
                content = re.sub(r"^##\s*第\d+页\s*$", "", content, flags=re.M)

            doc = LCDocument(
                page_content=content,
                metadata={
                    "source": str(rel_path),
                    "filename": md_file.name,
                    "category": parts[0] if len(parts) > 1 else "",
                    "type": _infer_type(rel_path),
                },
            )
            docs.append(doc)
        except Exception as e:
            print(f"  [SKIP] {md_file}: {e}")

    return docs


def chunk_documents(docs: list[LCDocument]) -> list[LCDocument]:
    """按递归字符拆分文档"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
        length_function=len,
    )
    return splitter.split_documents(docs)


def ingest_directory(data_dir: str) -> int:
    """入库整个目录：加载 → 分块 → 向量化 → 存储"""
    print(f"[ingest] 加载目录: {data_dir}")
    docs = load_markdown_files(data_dir)
    if not docs:
        print("[ingest] 未找到 .md 文件")
        return 0

    print(f"[ingest] 加载了 {len(docs)} 个文档，正在分块...")
    chunks = chunk_documents(docs)
    print(f"[ingest] 分块完成: {len(chunks)} 块")

    print(f"[ingest] 正在向量化并写入 pgvector...")
    vectorstore = create_vectorstore()

    # 批量写入（每批 50 个以防内存过大）
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectorstore.add_documents(batch)
        print(f"  [ingest] {min(i + batch_size, len(chunks))}/{len(chunks)}")

    print(f"[ingest] 完成！共入库 {len(chunks)} 个文档块")
    return len(chunks)


def ingest_single_file(file_path: str, source_name: str = "", filename: str = "") -> int:
    """入库单个文件（单文件=用户补充知识，默认 type=knowledge 参与分层检索）
    ponytail: 无 type 字段的块在方案B filter 下会被 SQL 排除，故必须给默认值
    filename 显式传入（上传场景为原文件名），否则用文件名兜底——
    避免 tempfile 随机名写入元数据导致列表/搜索/去重失效（review 修复）
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc = LCDocument(
        page_content=content,
        metadata={
            "source": source_name or os.path.basename(file_path),
            "filename": filename or os.path.basename(file_path),
            "category": "",
            "type": "knowledge",
        },
    )

    chunks = chunk_documents([doc])
    vectorstore = create_vectorstore()
    vectorstore.add_documents(chunks)
    return len(chunks)
