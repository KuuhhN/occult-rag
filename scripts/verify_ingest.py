"""验证 ingest 分层加载逻辑（dry-run，不写入数据库）"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.ingest import load_markdown_files

data_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/occult-ingest/knowledge-base"

docs = load_markdown_files(data_dir)
print(f"加载文档数: {len(docs)}")

# type 分布
types = Counter(d.metadata.get("type", "?") for d in docs)
print("\ntype 分布:")
for t, n in types.most_common():
    chars = sum(len(d.page_content) for d in docs if d.metadata.get("type") == t)
    print(f"  {t:12s}: {n:3d} 篇, {chars:>10,} 字符")

# 精排版 vs 原文
polished = [d for d in docs if d.metadata.get("type") == "polished"]
originals = [d for d in docs if d.metadata.get("type") == "original"]
print(f"\n精排版: {len(polished)} 篇 / 原文(兜底): {len(originals)} 篇")

# 抽查 metadata
print("\n抽查 3 篇:")
for d in docs[:3]:
    print(f"  source={d.metadata['source']}  type={d.metadata['type']}")
