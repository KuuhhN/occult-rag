"""ingest 分层逻辑单元测试（v0.2.1）"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.ingest import _infer_type, _is_redundant_original


def test_infer_type_mapping():
    """目录 → 层级标签映射"""
    assert _infer_type(Path("03-导读/塔罗冥想_导读.md")) == "guide"
    assert _infer_type(Path("05-摘要/塔罗冥想_摘要目录.md")) == "summary"
    assert _infer_type(Path("06-笔记/塔罗冥想_精读笔记.md")) == "note"
    assert _infer_type(Path("01-知识库/炼金术.md")) == "knowledge"
    assert _infer_type(Path("00-MOC/塔罗.md")) == "moc"
    assert _infer_type(Path("02-文献库/经典文献/塔罗冥想_原文.md")) == "original"
    assert _infer_type(Path("02-文献库/经典文献/塔罗冥想_精排版.md")) == "polished"


def test_infer_type_other():
    """未知目录 → other"""
    assert _infer_type(Path("某未知目录/文件.md")) == "other"
    assert _infer_type(Path("文件.md")) == "other"  # 根目录文件


def test_redundant_original_skips_when_polished_exists():
    """同书有精排版 → 原文跳过"""
    files = {Path("02-文献库/经典文献/塔罗冥想_原文.md"),
             Path("02-文献库/经典文献/塔罗冥想_精排版.md")}
    assert _is_redundant_original(
        Path("02-文献库/经典文献/塔罗冥想_原文.md"), files
    ) is True


def test_redundant_original_keeps_when_no_polished():
    """无精排版 → 原文保留（兜底）"""
    files = {Path("02-文献库/经典文献/塔罗冥想_原文.md")}
    assert _is_redundant_original(
        Path("02-文献库/经典文献/塔罗冥想_原文.md"), files
    ) is False


def test_redundant_original_nonstandard_name_kept():
    """非标准命名（书名原文.md）不触发跳过——避免误删"""
    files = {Path("02-文献库/经典文献/塔罗冥想原文.md"),
             Path("02-文献库/经典文献/塔罗冥想精排版.md")}
    assert _is_redundant_original(
        Path("02-文献库/经典文献/塔罗冥想原文.md"), files
    ) is False


def test_page_marker_cleanup():
    """页码标记清洗：独立整行删除，正文不受影响"""
    content = "## 第1页\n\n第一章 炼金术\n\n## 第2页\n正文内容\n\n### 第3页 小节标题\n"
    cleaned = re.sub(r"^##\s*第\d+页\s*$", "", content, flags=re.M)
    assert "## 第1页" not in cleaned
    assert "## 第2页" not in cleaned
    assert "第一章 炼金术" in cleaned
    assert "正文内容" in cleaned
    # ### 第3页 是三级标题（小节），不应被误删
    assert "### 第3页 小节标题" in cleaned


def test_page_marker_cleanup_only_for_original():
    """清洗仅对 _原文.md 生效：非标准命名文件不触发（与跳过判定一致）"""
    from pathlib import Path
    from app.rag.ingest import load_markdown_files
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "02-文献库").mkdir()
        # 标准原文：含页码标记
        (root / "02-文献库" / "测试书_原文.md").write_text(
            "## 第1页\n正文A\n", encoding="utf-8"
        )
        # 非标准命名：也含页码标记（不应被清洗）
        (root / "02-文献库" / "测试书原文.md").write_text(
            "## 第1页\n正文B\n", encoding="utf-8"
        )

        docs = load_markdown_files(root)
        by_name = {d.metadata["filename"]: d.page_content for d in docs}

        # 标准原文：页码被清洗
        assert "## 第1页" not in by_name["测试书_原文.md"]
        # 非标准命名：页码保留（不触发清洗）
        assert "## 第1页" in by_name["测试书原文.md"]


def test_skip_root_and_hidden_dirs():
    """vault 根目录文件（HOME.md）与隐藏目录（.tessdata）不入库"""
    import tempfile
    from pathlib import Path
    from app.rag.ingest import load_markdown_files

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "HOME.md").write_text("首页导航", encoding="utf-8")
        (root / ".tessdata").mkdir()
        (root / ".tessdata" / "sample.md").write_text("OCR 测试样本", encoding="utf-8")
        (root / "03-导读").mkdir()
        (root / "03-导读" / "测试_导读.md").write_text("导读内容", encoding="utf-8")

        docs = load_markdown_files(root)
        names = [d.metadata["filename"] for d in docs]
        assert "HOME.md" not in names          # 根目录文件跳过
        assert "sample.md" not in names        # 隐藏目录跳过
        assert "测试_导读.md" in names          # 正常目录内容保留
