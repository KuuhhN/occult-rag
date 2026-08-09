"""文档入库路由 — 上传 .md 文件或导入目录"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from ..models.schemas import IngestResponse
from ..rag.ingest import ingest_single_file, ingest_directory

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
async def ingest_file(file: UploadFile = File(...), source: str = Form("")):
    """上传单个 .md 文件并入库（≤10MB）"""
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="仅支持 .md 文件")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 10MB 上限")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content.decode("utf-8"))
        tmp_path = tmp.name

    try:
        count = ingest_single_file(tmp_path, source_name=source or file.filename)
        return IngestResponse(
            status="success",
            chunks_count=count,
            source=source or file.filename,
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
