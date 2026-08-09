"""应用配置 — 环境变量 + 默认值"""
import httpx
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/occult_rag"
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "qwen2.5:7b"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}

    def check_ollama(self) -> bool:
        """检测 Ollama 是否可用"""
        try:
            resp = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


settings = Settings()
