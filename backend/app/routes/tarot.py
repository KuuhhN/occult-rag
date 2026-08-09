"""塔罗抽牌互动路由：抽牌 → RAG 检索 → LLM 解读

牌意不硬编码——每张牌用牌名构造检索 query，从知识库（塔罗冥想等书籍）
检索相关章节，LLM 基于检索内容生成解读。真实 RAG 业务形态，可面试深挖。
"""
import asyncio
import logging
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..data.tarot_cards import ALL_CARDS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tarot", tags=["tarot"])


class DrawRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=3, description="抽牌张数（1-3）")
    question: str = Field(default="", max_length=500, description="问卜的问题（可选）")


def _draw_cards(count: int) -> list[dict]:
    """随机抽 count 张不重复牌，每张随机正逆位"""
    picked = random.sample(ALL_CARDS, min(count, len(ALL_CARDS)))
    return [
        {**card, "reversed": random.random() < 0.5}
        for card in picked
    ]


async def _retrieve_for_card(card: dict) -> list:
    """用牌名构造 query 检索知识库，返回相关块"""
    from ..rag.retrieve import retrieve

    orientation = "逆位" if card["reversed"] else "正位"
    query = f"{card['name_cn']} 塔罗牌 {orientation} 牌意 含义"
    try:
        return await asyncio.to_thread(retrieve, query, top_k=3)
    except Exception:
        logger.exception("塔罗牌检索失败: %s", card["name_cn"])
        return []




async def _generate_reading(cards_with_sources: list, question: str) -> list[str]:
    """逐张生成解读（每张卡独立 LLM 调用）

    之前一次调用生成全部解读，LLM 偶发只返回部分卡牌导致解读缺失
    （用户反馈"2、3张卡没有解读"）。改为逐张生成：count≤3，每次
    独立 prompt + 独立解析，缺失一张不影响其他张。
    """
    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.7,
    )
    q_line = f"\n问卜问题：{question}" if question.strip() else ""
    readings: list[str] = []
    for item in cards_with_sources:
        card, blocks = item["card"], item["blocks"]
        orientation = "逆位" if card["reversed"] else "正位"
        snippets = "\n".join(
            f"- {b.get('content', '')[:220]}" for b in blocks[:3]
        )
        prompt = (
            "你是神秘学塔罗解读师。基于下面检索到的资料，为这张牌生成一段"
            "60-100 字的中文解读（贴合牌的正逆位含义，若有问卜问题需结合问题）。"
            "直接输出 JSON 对象，格式：{\"interpretation\": \"...\"}，不要其他文字。\n\n"
            f"【{card['name_cn']}（{card['name_en']}）{orientation}】\n"
            f"检索到的资料：\n{snippets or '（知识库暂无直接相关内容，请基于塔罗学常识谨慎解读并标注）'}"
            f"{q_line}"
        )
        try:
            resp = await asyncio.to_thread(llm.invoke, prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            import json as _json
            data = _json.loads(text)
            reading = data if isinstance(data, dict) else {}
            readings.append(reading.get("interpretation", ""))
        except Exception:
            logger.exception("单张解读生成失败: %s", card["name_cn"])
            readings.append("")
    return readings


async def _generate_overall_reading(
    cards_with_sources: list, readings: list[str], question: str
) -> str:
    """生成综合解读（三张以上牌时）：把各牌解读汇总成整体趋势与建议

    单张牌不生成（单张解读已是整体）；失败时降级返回空字符串。
    """
    if len(cards_with_sources) < 2:
        return ""
    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.7,
    )
    # 汇总各牌信息（牌名 + 正逆位 + 单牌解读）
    summary = []
    for i, item in enumerate(cards_with_sources):
        card = item["card"]
        orientation = "逆位" if card["reversed"] else "正位"
        interp = readings[i] if i < len(readings) else ""
        summary.append(
            f"{i + 1}. {card['name_cn']}（{orientation}）：{interp}"
        )
    q_line = f"\n问卜问题：{question}" if question.strip() else ""
    prompt = (
        "你是神秘学塔罗解读师。下面是一次多张牌占卜的结果（各牌名+正逆位+单牌解读）。"
        "请给出一个综合解读（100-150 字中文）：把这些牌联系起来，找出共同主题与趋势，"
        "结合问卜问题给出整体建议。直接输出纯文本，不要标题和 JSON。\n\n"
        + "\n".join(summary)
        + q_line
    )
    try:
        resp = await asyncio.to_thread(llm.invoke, prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        return (text or "").strip()
    except Exception:
        logger.exception("综合解读生成失败")
        return ""


@router.post("/draw")
async def draw(request: DrawRequest):
    """抽牌：返回牌面 + RAG 解读 + 检索来源"""
    cards = _draw_cards(request.count)
    cards_with_sources = []
    all_sources = []
    for card in cards:
        blocks = await _retrieve_for_card(card)
        cards_with_sources.append({"card": card, "blocks": blocks})
        for b in blocks[:3]:
            all_sources.append({
                "filename": b.get("filename", ""),
                "type": b.get("type", ""),
                "score": round(1 - float(b.get("score", 0.0) or 0.0), 3),
            })
    readings = await _generate_reading(cards_with_sources, request.question)
    overall = await _generate_overall_reading(
        cards_with_sources, readings, request.question
    )

    result_cards = []
    for i, item in enumerate(cards_with_sources):
        card = item["card"]
        # 逐张生成的顺序即对应关系（readings[i] 是第 i 张卡的解读），
        # 不依赖 LLM 输出 card_id（LLM 幻觉会导致解读错位——修复过）
        interpretation = readings[i] if i < len(readings) else ""
        result_cards.append({
            "card_id": card["id"],
            "name_cn": card["name_cn"],
            "name_en": card["name_en"],
            "arcana": card.get("arcana", "major"),
            "suit": card.get("suit", ""),
            "reversed": card["reversed"],
            "interpretation": interpretation,
        })
    return {
        "cards": result_cards,
        "sources": all_sources[:6],
        "question": request.question,
        "overall": overall,
    }
