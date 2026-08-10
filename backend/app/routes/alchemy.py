# -*- coding: utf-8 -*-
"""炼金图像版块路由：图库列表 / 单图详情 / 附图解读（VLM+知识库检索）"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag.retrieve import retrieve
from app.rag.ingest import create_vectorstore

router = APIRouter(prefix="/alchemy", tags=["alchemy"])

# backend/app/routes/ → 项目根：向上 3 级（routes → app → backend → occult-rag）
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend")
IMG_DIR = os.path.join(FRONTEND, "public", "images", "alchemy")
META_JSON = os.path.join(IMG_DIR, "metadata.json")
INTERP_JSON = os.path.join(IMG_DIR, "interpretations.json")

# 缓存（图像与解读文件只在导入时变化）
_cache = {}


def _load() -> tuple[list, dict]:
    if "meta" not in _cache:
        _cache["meta"] = json.load(open(META_JSON, encoding="utf-8"))
        _cache["interp"] = {}
        if os.path.exists(INTERP_JSON):
            _cache["interp"] = json.load(open(INTERP_JSON, encoding="utf-8"))
    return _cache["meta"], _cache["interp"]


@router.get("/images")
async def list_images(book: str | None = None, page_type: str | None = None,
                      limit: int = 50, offset: int = 0):
    """图库列表：分页 + 按书/类型筛选"""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    meta, interp = _load()
    items = []
    for m in meta:
        if book and m["book"] != book:
            continue
        if page_type and m.get("page_type") != page_type:
            continue
        it = dict(m)
        it["summary"] = interp.get(m["id"], {}).get("summary", "")
        items.append(it)
    items.sort(key=lambda x: (x["book"], x["page"]))
    total = len(items)
    return {"total": total, "items": items[offset:offset + limit]}


@router.get("/images/{img_id:path}")
async def get_image(img_id: str):
    """单图详情：图 + 解读 + 关键词"""
    meta, interp = _load()
    m = next((x for x in meta if x["id"] == img_id), None)
    if not m:
        raise HTTPException(404, "图像不存在")
    info = interp.get(img_id, {})
    return {**m, "summary": info.get("summary", ""), "interpretation": info.get("interpretation", ""),
            "keywords": info.get("keywords", [])}


class InterpretRequest(BaseModel):
    image_id: str = Field(..., description="图像 id（如 real-alchemy/006-0.jpg）")
    question: str = Field(default="请解读这张炼金图像", description="用户对图的追问")
    top_k: int = Field(default=3, ge=1, le=8)


@router.post("/interpret")
async def interpret_image(req: InterpretRequest):
    """附图解读：VLM 解读（已有解读则复用）+ 检索知识库相关章节 → 综合回答"""
    meta, interp = _load()
    m = next((x for x in meta if x["id"] == req.image_id), None)
    if not m:
        raise HTTPException(404, "图像不存在")

    # 1. 图像解读（已生成则直接复用，零 API 调用）
    info = interp.get(req.image_id, {})
    image_text = info.get("interpretation") or info.get("summary") or ""

    # 2. 知识库检索（解读内容 + 用户问题 双查询）
    queries = [q for q in (req.question, image_text) if q]
    try:
        tasks = [asyncio.to_thread(retrieve, q, top_k=req.top_k) for q in queries[:2]]
        results = await asyncio.gather(*tasks)
        sources = [s for batch in results for s in batch][:req.top_k]
    except Exception as e:
        sources = []
        print(f"[alchemy] 检索失败: {e}", file=sys.stderr)

    # 3. 组装回答
    lines = []
    if image_text:
        lines.append(f"【图像解读】{image_text}")
    if sources:
        lines.append("\n【相关文献】")
        for i, s in enumerate(sources[:req.top_k], 1):
            lines.append(f"{i}. {s.get('content', '')[:120]}（来源：{s.get('source', '未知')}）")
    else:
        lines.append("\n（知识库未检索到相关章节）")
    return {
        "image": {**m, "summary": info.get("summary", "")},
        "answer": "\n".join(lines),
        "sources": sources,
    }


# 供聊天页附图使用：按文件名/关键词找图
@router.get("/search")
async def search_images(q: str = "", limit: int = 10):
    """按关键词/文件名搜索图像（解读关键词匹配）"""
    meta, interp = _load()
    ql = q.lower()
    hits = []
    for m in meta:
        info = interp.get(m["id"], {})
        kws = " ".join(info.get("keywords", [])) + info.get("summary", "")
        if ql and (ql in m["file"].lower() or ql in kws.lower()):
            hits.append({**m, "summary": info.get("summary", "")})
    return {"items": hits[:limit]}


# 向量化检索图像（多模态 RAG：问题 → 图像解读向量）
def embed_interpretations():
    """把图像解读向量化入 pgvector，供语义检索（调用方为启动脚本/导入脚本）"""
    from langchain_core.documents import Document
    meta, interp = _load()
    docs = []
    for m in meta:
        info = interp.get(m["id"], {})
        if not info.get("summary") and not info.get("interpretation"):
            continue
        text = f"炼金图像 {m['book_title']} 第{m['page']}页：{info.get('summary','')} {info.get('interpretation','')}"
        docs.append(Document(
            page_content=text,
            metadata={"source": f"炼金图像/{m['book_title']}/p{m['page']}", "type": "alchemy-image"},
        ))
    if not docs:
        return 0
    vs = create_vectorstore()
    vs.add_documents(docs)
    return len(docs)
