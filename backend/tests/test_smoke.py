"""冒烟测试（pytest）— 验证 RAG 管线各组件

运行: cd backend && python -m pytest tests/ -v
覆盖:
1. Embedding 模型可用性（nomic-embed-text）
2. PostgreSQL 连接 + pgvector 扩展
3. 文档分块
4. 向量化入库 + 语义检索（端到端）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from langchain_core.documents import Document as LCDocument

from app.config import settings
from app.rag.ingest import create_embeddings, chunk_documents


def test_embedding_model():
    """Embedding 模型返回 768 维向量"""
    emb = create_embeddings()
    vec = emb.embed_query("炼金术的核心原理")
    assert len(vec) == 768, f"维度={len(vec)}，应为 768"


def test_database_connection():
    """PostgreSQL 连接可达"""
    from app.database import check_connection
    assert check_connection(), "数据库连接失败"


def test_pgvector_extension():
    """pgvector 扩展已安装"""
    from sqlalchemy import text
    from app.database import _get_engine
    with _get_engine().connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar()
    assert version, "vector 扩展未安装"


def test_chunking():
    """长文档正确分块（>1 块，每块 ≤ chunk_size）"""
    para = "第一章 炼金术的起源。炼金术起源于古希腊时期的亚历山大城，融合了埃及的工艺、希腊的自然哲学与犹太的神秘主义传统。"
    doc = LCDocument(
        page_content="\n\n".join([para] * 25),
        metadata={"source": "test.md"},
    )
    chunks = chunk_documents([doc])
    assert len(chunks) > 1, f"分块数={len(chunks)} 过少"
    for c in chunks:
        assert len(c.page_content) <= settings.chunk_size + settings.chunk_overlap


def test_ingest_and_retrieve():
    """向量化 → 入库 → 语义检索（端到端）"""
    from app.rag.ingest import create_vectorstore

    vstore = create_vectorstore()
    test_doc = LCDocument(
        page_content="贤者之石是炼金术的终极目标，被认为是万物的转化之石。",
        metadata={"source": "pytest-smoke.md"},
    )
    vstore.add_documents([test_doc])

    results = vstore.similarity_search("贤者之石是什么？", k=1)
    assert results, "检索无结果"

    # 清理测试数据
    from sqlalchemy import text
    from app.database import _get_engine
    with _get_engine().connect() as conn:
        conn.execute(
            text("DELETE FROM langchain_pg_embedding WHERE cmetadata::text LIKE '%pytest-smoke%'")
        )
        conn.commit()
