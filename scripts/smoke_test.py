"""冒烟测试 — 验证 RAG 管线各组件

用法: python scripts/smoke_test.py
覆盖:
1. Embedding 模型可用性（nomic-embed-text）
2. PostgreSQL 连接 + pgvector
3. 文档分块
4. 向量化入库（写入 pgvector 并检索）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.rag.ingest import create_embeddings, chunk_documents
from langchain_core.documents import Document as LCDocument

PASS = 0
FAIL = 0


def check(name: str, fn):
    global PASS, FAIL
    try:
        result = fn()
        print(f"  [PASS] {name}" + (f" — {result}" if result else ""))
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {name} — {type(e).__name__}: {str(e)[:150]}")
        FAIL += 1


def main():
    print("=" * 50)
    print("  Occult-RAG 冒烟测试")
    print("=" * 50)
    print(f"  Ollama: {settings.ollama_base_url}")
    print(f"  Embedding: {settings.embedding_model}")
    print(f"  LLM: {settings.llm_model}")
    print(f"  DB: {settings.database_url}")
    print("=" * 50)

    # 1. Embedding
    def t_embedding():
        emb = create_embeddings()
        vec = emb.embed_query("炼金术的核心原理")
        return f"维度={len(vec)}"

    check("Embedding 模型 (nomic-embed-text)", t_embedding)

    # 2. 数据库连接
    def t_db():
        from app.database import check_connection
        ok = check_connection()
        assert ok, "连接失败"
        return "SELECT 1 OK"

    check("PostgreSQL 连接", t_db)

    # 3. pgvector 扩展
    def t_pgvector():
        from sqlalchemy import text
        from app.database import _get_engine
        with _get_engine().connect() as conn:
            r = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            version = r.scalar()
            assert version, "vector 扩展未安装"
            return f"pgvector {version}"

    check("pgvector 扩展", t_pgvector)

    # 4. 文档分块
    def t_chunk():
        # 生成 >2000 字符的测试文本，确保跨多个 chunk
        para = "第一章 炼金术的起源。炼金术起源于古希腊时期的亚历山大城，融合了埃及的工艺、希腊的自然哲学与犹太的神秘主义传统。"
        long_text = "\n\n".join([para] * 25)  # ~25 × 60 = 1500+ 字符
        doc = LCDocument(
            page_content=long_text,
            metadata={"source": "test.md"},
        )
        chunks = chunk_documents([doc])
        assert len(chunks) > 1, f"分块数={len(chunks)} 过少"
        return f"{len(chunks)} 块 (每块 ≤{settings.chunk_size} 字符)"

    check("文档分块", t_chunk)

    # 5. 向量化 + 入库 + 检索（端到端）
    def t_ingest_retrieve():
        from app.rag.ingest import create_vectorstore
        from langchain_core.documents import Document as D
        from sqlalchemy import text
        from app.database import _get_engine

        vstore = create_vectorstore()
        # 写入一条测试文档
        vstore.add_documents([
            D(page_content="贤者之石是炼金术的终极目标，被认为是万物的转化之石。",
              metadata={"source": "smoke-test.md"})
        ])
        # 检索
        results = vstore.similarity_search("贤者之石是什么？", k=1)
        assert results, "检索无结果"
        # 自清理：删除本测试写入的文档，避免污染知识库
        with _get_engine().connect() as conn:
            conn.execute(
                text("DELETE FROM langchain_pg_embedding WHERE cmetadata->>'source' = 'smoke-test.md'")
            )
            conn.commit()
        return f"检索命中: {results[0].page_content[:20]}..."

    check("向量化 + 入库 + 检索", t_ingest_retrieve)

    print("=" * 50)
    print(f"  结果: {PASS} 通过 / {FAIL} 失败")
    print("=" * 50)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
