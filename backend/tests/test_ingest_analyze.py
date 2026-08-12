# -*- coding: utf-8 -*-
"""一键入库+分析归纳 单元测试"""
import pytest

from app.models.schemas import AnalyzeResult, IngestResponse
from app.rag.summarize import _parse, build_note_md


class TestAnalyzeParse:
    def test_parse_full(self):
        r = _parse("摘要：塔罗冥想的核心方法\n导读：适合初学者\n关键词：塔罗、冥想、符号")
        assert r["summary"] == "塔罗冥想的核心方法"
        assert r["guide"] == "适合初学者"
        assert r["keywords"] == ["塔罗", "冥想", "符号"]

    def test_parse_missing_fields(self):
        r = _parse("摘要：只有摘要")
        assert r["summary"] == "只有摘要"
        assert r["guide"] == ""
        assert r["keywords"] == []

    def test_parse_keywords_comma_variants(self):
        r = _parse("关键词：A,B,C，D")
        assert r["keywords"] == ["A", "B", "C", "D"]


class TestBuildNote:
    def test_note_md_shape(self):
        md = build_note_md("测试书", {"summary": "S", "guide": "G", "keywords": ["K1", "K2"]})
        assert "# 测试书 — 资料导读" in md
        assert "> 类型：自动归纳（一键入库）" in md
        assert "## 摘要\n\nS" in md
        assert "## 导读\n\nG" in md
        assert "K1、K2" in md


class TestSchemas:
    def test_analyze_result_defaults(self):
        r = AnalyzeResult()
        assert r.summary == "" and r.guide == "" and r.keywords == []

    def test_ingest_response_with_analyze(self):
        resp = IngestResponse(status="success", chunks_count=2, source="x.md",
                              analyze=AnalyzeResult(summary="S", keywords=["k"]))
        assert resp.analyze.summary == "S"
        assert resp.analyze.keywords == ["k"]

    def test_ingest_response_without_analyze(self):
        resp = IngestResponse(status="success", chunks_count=1, source="y.md")
        assert resp.analyze is None
