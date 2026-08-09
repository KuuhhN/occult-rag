"""方案 B：问题分类器单元测试"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.retrieve import classify_question, _type_filter


def test_classify_overview():
    """概览类问题 → overview"""
    for q in [
        "塔罗冥想这本书主要讲了什么",
        "介绍一下赫尔墨斯主义的核心思想",
        "炼金术的概述",
        "这本书的结构是怎样的",
        "古代希腊仪式文化研究包含哪些内容",
    ]:
        assert classify_question(q) == "overview", f"误判: {q}"


def test_classify_detail():
    """细节类问题 → detail"""
    for q in [
        "贤者之石的颜色是什么",
        "如何制作点金石",
        "召唤仪式的具体步骤",
        "咒语怎么念",
        "占星术的定义是什么",
    ]:
        assert classify_question(q) == "detail", f"误判: {q}"


def test_classify_general():
    """无法判断 → general"""
    for q in [
        "你好",
        "你是谁",
        "塔罗牌",
        "神秘学",
    ]:
        assert classify_question(q) == "general", f"误判: {q}"


def test_type_filter():
    """分类 → metadata filter 映射（统一排除 background 背景文献）"""
    base = {"category": {"$ne": "background"}}
    assert _type_filter("overview") == {**base, "type": {"$in": ["note", "guide", "summary", "knowledge", "moc", "polished"]}}
    assert _type_filter("detail") == {**base, "type": {"$in": ["polished", "original"]}}
    assert _type_filter("general") == base  # general 也排除 background
