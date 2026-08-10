"""聊天路由 — RAG 问答 + SSE 流式响应（支持多轮对话）"""
import json
import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..models.schemas import ChatRequest, ChatResponse, SourceDoc
from ..config import settings
from ..rag.memory import get_memory

router = APIRouter(prefix="/chat", tags=["chat"])

# 环境就绪标志（import 时检查一次）
try:
    from ..rag.chain import get_rag_chain
    from ..rag.retrieve import retrieve
    _rag_available = True
except Exception:
    _rag_available = False

# 环境检查缓存（30s TTL，避免每请求最多 8s 的开销）
# ponytail: 30s TTL 缓存，若环境探测开销可接受可删
_env_cache: dict = {"ts": 0.0, "ok": False, "hint": ""}
_ENV_CACHE_TTL = 30.0


def _check_env():
    """检查运行环境，返回 (可用, 提示信息)。带 30s TTL 缓存。"""
    import time
    now = time.monotonic()
    if now - _env_cache["ts"] < _ENV_CACHE_TTL:
        return _env_cache["ok"], _env_cache["hint"]

    if not _rag_available:
        result = (False, "RAG 模块加载失败，请检查 Python 依赖是否安装完整。")
    elif not settings.check_ollama():
        result = (False, (
            "Ollama 服务未启动。请先安装并启动 Ollama，然后拉取模型：\n\n"
            "1. 下载 Ollama: https://ollama.com/download\n"
            "2. 启动后运行: ollama pull nomic-embed-text && ollama pull qwen2.5:7b"
        ))
    else:
        # 数据库检查（懒加载）
        try:
            from ..database import check_connection
            if not check_connection():
                result = (False, "数据库连接不可用，请检查 PostgreSQL 是否已启动。")
            else:
                result = (True, "")
        except Exception:
            result = (False, "数据库连接不可用，请检查 PostgreSQL 是否已启动。")

    _env_cache.update({"ts": now, "ok": result[0], "hint": result[1]})
    return result


def _resolve_conversation(conversation_id: str) -> str:
    """为空则生成新会话 ID"""
    # ponytail: 无鉴权会话，客户端可指定任意 ID；公网部署前改为服务端生成+绑定用户
    return conversation_id.strip() or uuid.uuid4().hex[:12]


FALLBACK_ANSWER = (
    "🜁 **神秘学顾问正在等待环境配置完成。**\n\n"
    "当前缺少以下组件，聊天功能暂不可用：\n\n"
    "| 组件 | 状态 | 说明 |\n"
    "|------|------|------|\n"
    f"| Ollama | {'✅' if settings.check_ollama() else '❌'} | 本地 LLM 服务 |\n"
    "| PostgreSQL + pgvector | 请启动 Docker | 向量数据库 |\n\n"
    "**快速启动步骤：**\n"
    "1. 安装 [Ollama](https://ollama.com/download) → 拉取模型\n"
    "2. 启动 Docker Desktop → `docker compose up -d db`\n"
    "3. 导入笔记 → `python scripts/import_notes.py ../occult-ingest/knowledge-base`\n"
    "4. 重启后端 → 刷新本页即可对话"
)

async def _do_retrieve(question: str, top_k: int, include_background: bool, retrieval_mode: str = "hybrid") -> list:
    """统一检索入口：hybrid（向量+BM25 RRF）或 vector（纯向量）

    额外并行检索炼金图像（alchemy-image 子集）：
    炼金图仅 364 条 vs 文档 6 万+，全库 top_k 永远排不进；单独
    对 alchemy-image 类型检索，保证相关话题能命中图像。
    """
    from ..rag.retrieve import retrieve
    from ..rag.ingest import create_vectorstore

    sources_raw = await asyncio.to_thread(
        retrieve, question, top_k=top_k, include_background=include_background
    )
    if retrieval_mode != "vector":
        try:
            from ..rag.hybrid import hybrid_retrieve

            sources_raw = await asyncio.to_thread(
                hybrid_retrieve,
                question, top_k,
                sources_raw,
                include_background=include_background,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("混合检索失败，回退纯向量")

    # 单独检索炼金图像（保证相关话题必有图）
    try:
        vs = create_vectorstore()
        img_docs = await asyncio.to_thread(
            vs.similarity_search, question, k=3,
            filter={"type": "alchemy-image"},
        )
        img_sources = [
            {
                "content": d.page_content,
                "source": d.metadata.get("source", ""),
                "filename": d.metadata.get("filename", ""),
                "category": d.metadata.get("category", ""),
                "type": "alchemy-image",
                "score": 0.0,
            }
            for d in img_docs
        ]
        # 合并（炼金图排前，保证被提取）
        sources_raw = img_sources + sources_raw
    except Exception:
        import logging
        logging.getLogger(__name__).exception("炼金图检索失败，忽略")
    return sources_raw


def _extract_alchemy_images(sources_raw: list) -> list:
    """从检索结果中提取炼金图像（type=alchemy-image），供自动附图

    source 格式：炼金图像/{book_title}/p{page}；用 metadata.json 反查真实 file。
    """
    from ..models.schemas import AlchemyImage
    import json
    import os
    import re

    # 加载炼金图 metadata（book_title → 真实 file 路径）
    meta_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "frontend",
        "public", "images", "alchemy", "metadata.json")
    try:
        meta = json.load(open(meta_path, encoding="utf-8"))
        meta_by_source = {}
        for m in meta:
            key = f"炼金图像/{m['book_title']}/p{m['page']}"
            meta_by_source[key] = m
    except Exception:
        meta_by_source = {}

    images = []
    seen_ids = set()
    for s in sources_raw:
        if s.get("type") != "alchemy-image":
            continue
        src = s.get("source", "")
        m = meta_by_source.get(src)
        if not m:
            continue
        img_id = m.get("id", "")
        if img_id in seen_ids:
            continue
        seen_ids.add(img_id)
        content = s.get("content", "")
        images.append(AlchemyImage(
            id=img_id,
            file=m.get("file", ""),
            summary=content.split("：", 1)[-1][:80] if "：" in content else "",
            book_title=m.get("book_title", ""),
            page=int(m.get("page", 0) or 0),
        ))
        if len(images) >= 3:
            break
    return images


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """RAG 问答（非流式，多轮对话）"""
    conversation_id = _resolve_conversation(request.conversation_id)
    memory = get_memory()

    env_ok, env_hint = await asyncio.to_thread(_check_env)
    if not env_ok:
        return ChatResponse(
            answer=FALLBACK_ANSWER + f"\n\n> 💡 {env_hint}",
            sources=[],
            conversation_id=conversation_id,
        )

    try:
        history = memory.get_history(conversation_id)
        chain = get_rag_chain()
        answer = await chain.ainvoke({
            "question": request.question,
            "history": history,
        })

        # 存入会话记忆（只存干净的问答，不存检索片段）
        memory.add(conversation_id, "user", request.question)
        memory.add(conversation_id, "assistant", answer)

        # 同步检索放线程池，避免阻塞事件循环
        sources_raw = await _do_retrieve(request.question, request.top_k, request.include_background, request.retrieval_mode)
        sources = [
            SourceDoc(
                content=s["content"][:200],
                source=s.get("source", ""),
                page_range="",
                score=s.get("score", 0.0),
                type=s.get("type", ""),
                filename=s.get("filename", ""),
            )
            for s in sources_raw
        ]
        images = _extract_alchemy_images(sources_raw)
        return ChatResponse(answer=answer, sources=sources, images=images,
                            conversation_id=conversation_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("RAG 问答失败")
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试。详细信息已记录到日志。")


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """RAG 问答（SSE 流式，多轮对话）"""
    conversation_id = _resolve_conversation(request.conversation_id)
    memory = get_memory()
    env_ok, env_hint = await asyncio.to_thread(_check_env)

    async def event_generator():
        if not env_ok:
            # 降级模式：返回提示信息
            for char in FALLBACK_ANSWER:
                yield {"event": "token", "data": char}
                await asyncio.sleep(0.01)
            yield {"event": "done", "data": json.dumps(
                {"answer": FALLBACK_ANSWER, "conversation_id": conversation_id},
                ensure_ascii=False,
            )}
            return

        try:
            history = memory.get_history(conversation_id)
            chain = get_rag_chain()

            # 同步检索放线程池，避免阻塞事件循环
            sources_raw = await _do_retrieve(request.question, request.top_k, request.include_background, request.retrieval_mode)
            # 暴露检索策略（方案 B 分层检索的 question_type）
            from ..rag.retrieve import classify_question
            qtype = classify_question(request.question)
            qtype_desc = {
                "overview": "概览（优先笔记层：导读/摘要/精读/知识条目）",
                "detail": "细节（优先精排版/原文层）",
                "general": "通用（全层检索，排除背景文献）",
            }.get(qtype, qtype)
            yield {
                "event": "meta",
                "data": json.dumps(
                    {"question_type": qtype, "description": qtype_desc},
                    ensure_ascii=False,
                ),
            }
            sources_data = [
                {
                    "content": s["content"][:200],
                    "source": s.get("source", ""),
                    "filename": s.get("filename", ""),
                    "score": s.get("score", 0.0),
                    "type": s.get("type", ""),
                }
                for s in sources_raw
            ]
            yield {"event": "sources", "data": json.dumps(sources_data, ensure_ascii=False)}

            # 自动附带的炼金图像（检索命中时）
            images = _extract_alchemy_images(sources_raw)
            if images:
                yield {"event": "images", "data": json.dumps(
                    [img.model_dump() for img in images], ensure_ascii=False,
                )}

            full_answer = ""
            async for chunk in chain.astream({
                "question": request.question,
                "history": history,
            }):
                full_answer += chunk
                yield {"event": "token", "data": chunk}

            # 流式完成后存入记忆
            memory.add(conversation_id, "user", request.question)
            memory.add(conversation_id, "assistant", full_answer)

            yield {"event": "done", "data": json.dumps(
                {"answer": full_answer, "conversation_id": conversation_id},
                ensure_ascii=False,
            )}

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("RAG 流式问答失败")
            # 脱敏：不向客户端暴露内部异常细节
            yield {"event": "error", "data": "服务器内部错误，请稍后重试。详细信息已记录到日志。"}

    return EventSourceResponse(event_generator())


@router.post("/followups")
async def followups(request: dict):
    """基于问答生成 2-3 条建议问题（回答完成后前端异步调用）"""
    question = (request.get("question") or "").strip()
    answer = (request.get("answer") or "")[:2000]
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        from ..config import settings
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.3,
        )
        prompt = (
            "基于下面的用户问题和 AI 回答，生成 2-3 条用户可能会继续追问的短问题。"
            "直接输出 JSON 数组字符串，例如 [\"问题1\", \"问题2\"]，不要其他文字。\n\n"
            f"用户问题：{question}\nAI 回答：{answer}"
        )
        resp = await asyncio.to_thread(llm.invoke, prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        # 提取 JSON 数组（容错：剥离可能的 markdown 代码块）
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        import json as _json
        items = _json.loads(text)
        if isinstance(items, list):
            return {"followups": [str(i) for i in items][:4]}
    except Exception:
        import logging
        logging.getLogger(__name__).exception("followups 生成失败")
    return {"followups": []}


@router.get("/{conversation_id}/history")
async def get_conversation_history(conversation_id: str):
    """获取指定会话的完整历史（前端切换会话时回显）"""
    memory = get_memory()
    history = memory.get_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": history}


@router.delete("/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """清空指定会话的历史"""
    memory = get_memory()
    memory.clear(conversation_id)
    return {"status": "cleared", "conversation_id": conversation_id}


@router.get("/conversations")
async def list_conversations(limit: int = 20):
    """列出最近会话（调试/管理用）"""
    memory = get_memory()
    return {"conversations": memory.list_conversations(limit=limit)}


@router.patch("/{conversation_id}")
async def rename_conversation(conversation_id: str, payload: dict):
    """重命名会话（payload: {"title": "..."}）"""
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title 不能为空")
    memory = get_memory()
    if not memory.rename(conversation_id, title):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "renamed", "conversation_id": conversation_id, "title": title}
