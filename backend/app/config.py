"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"

RetrievalMode = Literal["vector", "hybrid", "hybrid_rerank"]


class Settings(BaseSettings):
    """All runtime configuration. Field names map to upper-case env vars."""

    # Resolve the repository-root .env regardless of whether uvicorn/RQ starts in backend/.
    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        extra="ignore",
        case_sensitive=False,
    )

    # Gemini Developer API (free tier, subject to Google's quotas and availability).
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    # Embeddings run locally; no paid embedding API is used.
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    mock_llm: bool = False
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 60
    bcrypt_rounds: int = Field(default=12, ge=4, le=15)
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=150, ge=0)
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_mode: RetrievalMode = "hybrid"
    score_threshold: float | None = None
    rerank_threshold: float = 0.3
    max_upload_mb: int = Field(default=20, ge=1)
    cache_ttl_seconds: int = 86400
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    data_dir: str = "./data"
    database_url: str = ""
    redis_url: str = ""
    eval_results_path: str = "../eval/results/results.json"
    sample_docs_dir: str = "../eval/sample_docs"
    candidates_n: int = 20
    fused_n: int = 10
    embed_batch_size: int = 64

    @property
    def effective_score_threshold(self) -> float:
        """Cosine-similarity floor. Mock embeddings are sparser, so their default is lower."""
        if self.score_threshold is not None:
            return self.score_threshold
        return 0.12 if self.mock_llm else 0.25

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def resolve(self, value: str) -> Path:
        """Resolve a path setting relative to the backend directory, not the cwd."""
        path = Path(value).expanduser()
        return path if path.is_absolute() else (BASE_DIR / path).resolve()

    @property
    def data_path(self) -> Path:
        return self.resolve(self.data_dir)

    @property
    def uploads_path(self) -> Path:
        return self.data_path / "uploads"

    @property
    def chroma_path(self) -> Path:
        return self.data_path / "chroma"

    @property
    def sqlite_path(self) -> Path:
        return self.data_path / "documind.db"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object."""
    return Settings()
