"""数据库 — SQLAlchemy sync + pgvector（同步引擎，兼容 Windows 事件循环）

设计说明：
- 使用同步 SQLAlchemy 引擎，彻底绕开 Windows ProactorEventLoop 与 psycopg3
  异步模式不兼容的问题（langchain_postgres.PGVector 本来就是同步接口）
- 懒加载：不在 import 时连接，首次调用才创建引擎（降级友好）
- 不定义业务表模型：向量表由 LangChain PGVector 首次入库时自动创建
"""
import logging

from sqlalchemy import create_engine, text

from .config import settings

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    """懒加载同步引擎（短连接超时，快速失败）"""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            echo=False,
            pool_size=5,
            connect_args={"connect_timeout": 3},
        )
    return _engine


def check_connection() -> bool:
    """快速检查数据库是否可达"""
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database check failed: {e}")
        return False


def dispose_engine():
    """关闭连接池（释放资源）"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
