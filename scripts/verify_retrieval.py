"""验证分层检索：查询各代表性问题的命中层级分布（dry-run，只检索不生成）"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.rag.retrieve import retrieve

QUERIES = [
    ("概览", "塔罗冥想这本书主要讲了什么"),
    ("结构", "塔罗冥想的章节结构"),
    ("术语", "什么是贤者之石"),
    ("细节", "赫尔墨斯主义的核心思想"),
]

for label, q in QUERIES:
    results = retrieve(q, top_k=10)
    types = Counter(r["type"] for r in results)
    print(f"[{label}] {q}")
    print(f"  top-10 命中: {dict(types)}")
    for r in results[:3]:
        print(f"    {r['type']:10s} {r['source']}")
