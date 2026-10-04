from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    google_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    internal_service_token: SecretStr
    vector_store_type: Literal["chroma"] = "chroma"
    vector_store_path: Path = Path("./data/chroma")
    metadata_db_path: Path = Path("./data/documents.sqlite3")
    max_upload_size_mb: int = 20
    max_document_pages: int = 200
    max_extracted_chars: int = 2_000_000
    max_review_content_chars: int = 100_000
    max_chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_count: int = 5
    similarity_threshold: float = 0.25
    provider_timeout_seconds: float = 30
    provider_max_retries: int = 2
    max_concurrent_llm_requests: int = 4
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_limits_and_credentials(self) -> "Settings":
        if self.app_env != "test" and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required outside the test environment")
        if len(self.internal_service_token.get_secret_value()) < 32:
            raise ValueError("INTERNAL_SERVICE_TOKEN must contain at least 32 characters")
        if self.max_chunk_size <= 0 or not 0 <= self.chunk_overlap < self.max_chunk_size:
            raise ValueError("CHUNK_OVERLAP must be non-negative and smaller than MAX_CHUNK_SIZE")
        if min(self.max_upload_size_mb, self.max_document_pages, self.max_extracted_chars) <= 0:
            raise ValueError("Upload and document limits must be positive")
        if self.provider_max_retries < 0 or self.max_concurrent_llm_requests <= 0:
            raise ValueError("Provider retry and concurrency limits are invalid")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
