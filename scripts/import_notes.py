"""
批量导入脚本 — 将 occult-ingest 知识库笔记导入 RAG 系统

用法：
    # 导入 occult-ingest 知识库（需要先 clone 在旁边）
    python scripts/import_notes.py /path/to/occult-ingest/knowledge-base

    # 导入任意目录
    python scripts/import_notes.py /path/to/markdown/files

    # 先清空旧数据再导入（避免重复）
    python scripts/import_notes.py /path/to/markdown/files --clear

环境变量（与后端相同）：
    DATABASE_URL   — PostgreSQL 连接串
    OLLAMA_BASE_URL — Ollama 地址
"""
import sys
import os
import logging

# 将 backend 加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.rag.ingest import ingest_directory
from app.database import _get_engine
from sqlalchemy import text


def clear_documents():
    """清空 pgvector 中本 collection 的文档块（防止重复导入）"""
    from app.rag.ingest import COLLECTION_NAME

    # 按 collection 名子查询定位 uuid（不依赖库私有属性 _collection_id，
    # 该属性在未触发 create_collection 时为 None 会导致 DELETE 静默失效）
    with _get_engine().connect() as conn:
        result = conn.execute(
            text(
                "DELETE FROM langchain_pg_embedding "
                "WHERE collection_id = (SELECT uuid FROM langchain_pg_collection "
                "WHERE name = :name LIMIT 1)"
            ),
            {"name": COLLECTION_NAME},
        )
        conn.commit()
        print(f"🗑️  已清空本 collection 旧数据（{result.rowcount} 行）")


def mask_database_url(url: str) -> str:
    """脱敏连接串：隐藏密码，只显示 user/host/db"""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    userinfo = parts.username or ""
    if parts.password:
        userinfo += ":****"
    netloc = f"{userinfo}@{parts.hostname}" if userinfo else parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def main():
    args = sys.argv[1:]
    clear = "--clear" in args
    args = [a for a in args if a != "--clear"]

    if len(args) < 1:
        print("用法: python scripts/import_notes.py <笔记目录> [--clear]")
        print("示例: python scripts/import_notes.py /tmp/occult-ingest/knowledge-base --clear")
        sys.exit(1)

    data_dir = args[0]
    if not os.path.isdir(data_dir):
        print(f"❌ 目录不存在: {data_dir}")
        sys.exit(1)

    print("=" * 50)
    print("  神秘学顾问 · RAG 知识库导入")
    print("=" * 50)
    print(f"  数据源: {data_dir}")
    print(f"  PG 连接: {mask_database_url(settings.database_url)}")
    print(f"  Ollama: {settings.ollama_base_url}")
    print(f"  Embedding: {settings.embedding_model}")
    print(f"  分块大小: {settings.chunk_size} / 重叠: {settings.chunk_overlap}")
    print("=" * 50)
    print()

    if clear:
        try:
            confirm = input("⚠️ 将清空当前 collection 全部文档块并重新导入，确认？(y/N): ")
        except EOFError:
            confirm = ""  # 非交互环境视为取消，避免裸 traceback
        if confirm.strip().lower() != "y":
            print("已取消")
            sys.exit(0)

    try:
        if clear:
            clear_documents()
        count = ingest_directory(data_dir)
        print()
        print(f"✅ 成功！共导入 {count} 个文档块到 pgvector")
        print(f"   现在可以启动后端: docker compose up backend")
        print(f"   然后打开 http://localhost:3000 开始提问")
    except Exception as e:
        # 只输出异常类型，详情进 logging（避免回显连接细节）
        print(f"❌ 导入失败: {type(e).__name__}（详情见日志）")
        logging.exception("导入失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
