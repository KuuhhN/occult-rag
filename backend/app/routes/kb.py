"""知识库管理路由：统计面板 + 文档列表（供前端 /kb 页面使用）"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from ..database import _get_engine

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/stats")
async def kb_stats():
    """知识库统计：总块数 / type 分布 / category 分布 / 文档数"""
    with _get_engine().connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM langchain_pg_embedding")
        ).scalar()

        by_type = dict(conn.execute(
            text("SELECT cmetadata->>'type' AS t, COUNT(*) FROM langchain_pg_embedding GROUP BY 1 ORDER BY 2 DESC")
        ).fetchall())

        by_category = dict(conn.execute(
            text("SELECT COALESCE(cmetadata->>'category', 'core') AS c, COUNT(*) FROM langchain_pg_embedding GROUP BY 1 ORDER BY 2 DESC")
        ).fetchall())

        doc_count = conn.execute(
            text("SELECT COUNT(DISTINCT cmetadata->>'filename') FROM langchain_pg_embedding")
        ).scalar()

    return {
        "total_chunks": total,
        "documents": doc_count,
        "by_type": by_type,
        "by_category": by_category,
    }


@router.get("/documents")
async def kb_documents(
    q: str = Query("", description="按文件名模糊搜索"),
    type_filter: str = Query("", description="按层级过滤：polished/note/guide/..."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """文档列表：文件名 / 类型 / category / 块数（支持搜索与层级过滤）"""
    clauses = []
    params = {"limit": limit, "offset": offset}
    if q:
        clauses.append("cmetadata->>'filename' LIKE :q")
        params["q"] = f"%{q}%"
    if type_filter:
        clauses.append("cmetadata->>'type' = :tf")
        params["tf"] = type_filter
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with _get_engine().connect() as conn:
        rows = conn.execute(text(
            f"""
            SELECT COALESCE(cmetadata->>'filename', cmetadata->>'source', '（未知文档）') AS filename,
                   COALESCE(cmetadata->>'type', 'unknown') AS type,
                   COALESCE(cmetadata->>'category', 'core') AS category,
                   COUNT(*) AS chunks
            FROM langchain_pg_embedding
            {where}
            GROUP BY 1, 2, 3
            ORDER BY chunks DESC
            LIMIT :limit OFFSET :offset
            """
        ), params).fetchall()

        total = conn.execute(text(
            f"""
            SELECT COUNT(DISTINCT cmetadata->>'filename')
            FROM langchain_pg_embedding
            {where}
            """
        ), params).scalar()

    return {
        "documents": [
            {"filename": r[0], "type": r[1], "category": r[2], "chunks": r[3]}
            for r in rows
        ],
        "total": total,
    }
