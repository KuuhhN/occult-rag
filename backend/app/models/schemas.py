"""Pydantic 请求/响应模型"""
import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: str = Field(
        default="", max_length=64,
        description="会话 ID（多轮对话用；为空则开启新会话）",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="检索文档数（设置页可调）")
    include_background: bool = Field(
        default=False, description="是否包含背景文献（默认排除）"
    )
    retrieval_mode: str = Field(
        default="hybrid",
        description="检索模式：hybrid（向量+BM25 RRF 融合，默认）/ vector（纯向量）",
    )


class SourceDoc(BaseModel):
    content: str
    source: str = ""
    page_range: str = ""
    score: float | None = None   # 余弦距离（越小越相似）；None = BM25 独有块（无语义距离）
    type: str = ""              # 命中层级：polished/original/note/guide/summary/knowledge/moc
    filename: str = ""          # 来源文件名


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceDoc] = []
    conversation_id: str = Field(default="", description="会话 ID（客户端保存用于多轮对话）")


class AnalyzeResult(BaseModel):
    summary: str = ""
    guide: str = ""
    keywords: list[str] = []


class IngestResponse(BaseModel):
    status: str
    chunks_count: int
    source: str = ""
    analyze: AnalyzeResult | None = None


class HealthResponse(BaseModel):
    status: str
    ollama: str = "unknown"
    database: str = "unknown"
