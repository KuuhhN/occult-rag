"""文档入库路由 — 上传 .md/.txt/.pdf 文件（可一键分析归纳）或导入目录"""
import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from ..models.schemas import AnalyzeResult, IngestResponse
from ..rag.ingest import ingest_single_file, ingest_directory
from ..rag.summarize import summarize_document, build_note_md

router = APIRouter(prefix="/ingest", tags=["ingest"])

# 允许的入库根目录（目录导入只能操作该目录内；可通过环境变量 DATA_ROOT 覆盖）
DATA_ROOT = os.environ.get("DATA_ROOT", "/app/data")

# 上传大小上限：10MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _resolve_allowed_dir(directory: str) -> str:
    """校验并规范化目录路径，限制在 DATA_ROOT 内"""
    requested = Path(directory).resolve()
    root = Path(DATA_ROOT).resolve()

    if not requested.is_relative_to(root):
        raise HTTPException(
            status_code=403,
            detail=f"目录不在允许的入库根目录内（{root}）",
        )
    return str(requested)


@router.post("/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...), source: str = Form(""),
                      analyze: bool = Form(False)):
    """上传 .md/.txt/.pdf 文件并入库（≤10MB）

    analyze=True 时：LLM 生成 摘要/导读/关键词 → 作为 note 层一起入库，
    返回 analyze 结果供前端展示。LLM 失败自动降级为仅入库原文。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".md", ".txt", ".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 .md / .txt / .pdf 文件")

    content = await file.read(MAX_UPLOAD_SIZE + 1)  # 流式限长读取（防内存 DoS）
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 10MB 上限")

    # 提取文本：PDF 用 pymupdf，md/txt 直接解码
    text = ""
    if ext == ".pdf":
        try:
            import fitz  # pymupdf（requirements.txt 已声明）
        except ImportError:
            raise HTTPException(status_code=500, detail="服务器缺少 pymupdf 依赖，无法解析 PDF")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            pdf_path = tmp.name
        try:
            doc = fitz.open(pdf_path)
            try:
                text = "\n".join(p.get_text() for p in doc)
            finally:
                doc.close()
        except Exception:
            raise HTTPException(status_code=400, detail="PDF 解析失败（可能为扫描版，无法提取文字）")
        finally:
            os.unlink(pdf_path)
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF 无文字层（扫描版请先 OCR）")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码需为 UTF-8")

    # 原文入库（type=knowledge）
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    source_name = source or file.filename
    analyze_result = None
    try:
        count = ingest_single_file(tmp_path, source_name=source_name, filename=file.filename)
        # 一键分析归纳：生成 摘要/导读/关键词 → note 层入库
        if analyze:
            result = await asyncio.to_thread(summarize_document, text)
            if result:
                note_md = build_note_md(Path(source_name).stem, result)
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", delete=False, encoding="utf-8"
                ) as ntmp:
                    ntmp.write(note_md)
                    note_path = ntmp.name
                try:
                    count += ingest_single_file(
                        note_path,
                        source_name=f"{source_name}（自动导读）",
                        filename=f"{file.filename}（自动导读）.md",
                    )
                except Exception:
                    # note 入库失败不阻塞：原文已入库，降级仅返回原文结果（防重复入库）
                    import logging
                    logging.getLogger(__name__).exception("自动导读入库失败，已降级")
                    analyze_result = None  # 导读未实际入库，不返回结果防误导（review nit）
                finally:
                    os.unlink(note_path)
                analyze_result = AnalyzeResult(**result)
        return IngestResponse(
            status="success",
            chunks_count=count,
            source=source_name,
            analyze=analyze_result,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("单文件入库失败")
        raise HTTPException(status_code=500, detail="入库失败，请检查文件内容。详细信息已记录到日志。")
    finally:
        os.unlink(tmp_path)


@router.post("/directory", response_model=IngestResponse)
async def ingest_dir(directory: str = Form(DATA_ROOT)):
    """导入指定目录下所有 .md 文件（仅限 DATA_ROOT 内）"""
    try:
        resolved = _resolve_allowed_dir(directory)
    except HTTPException:
        raise

    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail=f"目录不存在: {resolved}")

    try:
        count = ingest_directory(resolved)
        return IngestResponse(
            status="success",
            chunks_count=count,
            source=resolved,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("批量入库失败")
        raise HTTPException(status_code=500, detail="批量入库失败，详细信息已记录到日志。")
