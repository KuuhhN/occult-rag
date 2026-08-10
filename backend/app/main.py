"""FastAPI 主入口"""
import asyncio
import os
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import alchemy, chat, ingest, kb, tarot
from .models.schemas import HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时检测数据库（失败则降级）；向量表由 LangChain 首次入库自动创建"""
    try:
        from .database import check_connection
        db_ok = await asyncio.to_thread(check_connection)
        logger.info("Database OK" if db_ok else "Database unavailable — degraded mode")
        if db_ok:
            # 幂等迁移：混合检索（BM25）的 tsvector 列/索引
            from .rag.ingest import ensure_tsvector
            await asyncio.to_thread(ensure_tsvector)
            logger.info("tsvector ready")
    except Exception as e:
        logger.warning(f"Database unavailable — degraded mode: {e}")
    yield
    try:
        from .database import dispose_engine
        await asyncio.to_thread(dispose_engine)
    except Exception:
        pass


app = FastAPI(
    title="神秘学顾问 · Occult RAG",
    description="基于 RAG 的神秘学知识问答系统 — LangChain + pgvector + Ollama",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(kb.router)
app.include_router(tarot.router)
app.include_router(alchemy.router)

# 炼金图像静态服务（/static/alchemy/<book>/<file>）
_static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "images", "alchemy")
if os.path.isdir(_static_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static/alchemy", StaticFiles(directory=_static_dir), name="alchemy-images")


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    db_status = "unknown"
    ollama_status = "unknown"

    try:
        from .database import check_connection
        db_ok = await asyncio.to_thread(check_connection)
        db_status = "ok" if db_ok else "unavailable"
    except Exception:
        db_status = "unavailable"

    ollama_status = "ok" if settings.check_ollama() else "unavailable"

    return HealthResponse(
        status="ok" if db_status == "ok" and ollama_status == "ok" else "degraded",
        ollama=ollama_status,
        database=db_status,
    )
