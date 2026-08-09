"""多轮对话记忆单元测试"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.memory import SessionMemory, format_history


def test_add_and_get():
    m = SessionMemory(max_turns=3)
    m.add("c1", "user", "问题1")
    m.add("c1", "assistant", "回答1")
    hist = m.get_history("c1")
    assert len(hist) == 2
    assert hist[0] == {"role": "user", "content": "问题1"}
    assert hist[1] == {"role": "assistant", "content": "回答1"}


def test_max_turns_truncation():
    """超过 max_turns 轮时丢弃最旧消息"""
    m = SessionMemory(max_turns=2)
    for i in range(5):
        m.add("c1", "user", f"问题{i}")
        m.add("c1", "assistant", f"回答{i}")
    hist = m.get_history("c1")
    # 最多保留 2 轮 = 4 条，且是最新的
    assert len(hist) == 4
    assert hist[0]["content"] == "问题3"
    assert hist[-1]["content"] == "回答4"


def test_clear():
    m = SessionMemory(max_turns=3)
    m.add("c1", "user", "问题1")
    m.clear("c1")
    assert m.get_history("c1") == []


def test_conversation_isolation():
    """不同会话互不影响"""
    m = SessionMemory(max_turns=3)
    m.add("a", "user", "A的问题")
    m.add("b", "user", "B的问题")
    assert m.get_history("a") == [{"role": "user", "content": "A的问题"}]
    assert m.get_history("b") == [{"role": "user", "content": "B的问题"}]


def test_format_history():
    m = SessionMemory(max_turns=3)
    m.add("c1", "user", "什么是贤者之石？")
    m.add("c1", "assistant", "贤者之石是炼金术的终极目标。")
    text = format_history(m.get_history("c1"))
    assert "用户: 什么是贤者之石？" in text
    assert "顾问: 贤者之石是炼金术的终极目标。" in text


def test_format_history_empty():
    assert format_history([]) == ""


def test_list_conversations_order():
    m = SessionMemory(max_turns=3)
    m.add("old", "user", "早的消息")
    m.add("new", "user", "新的消息")
    convs = m.list_conversations()
    # 按最后活跃时间倒序：new 在前
    assert convs[0]["conversation_id"] == "new"
    assert convs[1]["conversation_id"] == "old"
