"""塔罗抽牌：解读与卡牌按序绑定测试（防止 card_id 幻觉导致解读错位回归）"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routes.tarot import _draw_cards, _generate_reading  # noqa: E402


class _FakeResp:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    """mock ChatOllama：按调用顺序返回解读（模拟 LLM 顺序生成）"""

    def __init__(self, outputs: list[str]):
        self.outputs = outputs

    def invoke(self, prompt: str):
        idx = self._idx if hasattr(self, "_idx") else 0
        self._idx = idx + 1
        return _FakeResp(self.outputs[idx] if idx < len(self.outputs) else '{"interpretation": ""}')


def test_readings_order_matches_cards(monkeypatch):
    """逐张生成的解读必须与卡牌顺序一一对应（修复 card_id 幻觉错位）"""
    cards = _draw_cards(3)
    cards_with_sources = [{"card": c, "blocks": []} for c in cards]

    expected = [
        f'{{"interpretation": "{cards[0]["name_cn"]}的专属解读"}}',
        f'{{"interpretation": "{cards[1]["name_cn"]}的专属解读"}}',
        f'{{"interpretation": "{cards[2]["name_cn"]}的专属解读"}}',
    ]

    # monkeypatch langchain_ollama.ChatOllama（_generate_reading 函数内局部导入）
    import langchain_ollama

    fake = _FakeLLM(expected)
    monkeypatch.setattr(langchain_ollama, "ChatOllama", lambda **kw: fake)

    readings = asyncio.run(_generate_reading(cards_with_sources, ""))

    # 断言：readings[i] 是第 i 张卡的解读（含第 i 张牌名）
    assert len(readings) == 3
    assert cards[0]["name_cn"] in readings[0]
    assert cards[1]["name_cn"] in readings[1]
    assert cards[2]["name_cn"] in readings[2]
    # 且不与其他卡错位（第 0 张的解读不含第 1 张牌名）
    assert cards[1]["name_cn"] not in readings[0]
