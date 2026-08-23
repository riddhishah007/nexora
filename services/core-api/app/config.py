from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"

    database_url: str = (
        "postgresql://nexora:nexora_dev_password@postgres:5432/nexora"
    )

    jwt_secret: str = "change_me_to_a_long_random_string"
    refresh_token_secret: str = "change_me_to_a_different_long_random_string"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    core_api_port: int = 8000
    cors_allowed_origins: str = "http://localhost:3000"

    llm_provider: str = "gemini"  # gemini | groq

    gemini_api_key: str = ""

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_lite: str = "openai/gpt-oss-20b"
    groq_model_flash: str = "qwen/qwen3.6-27b"
    groq_model_pro: str = "openai/gpt-oss-120b"

    llm_model_lite: str = "gemini-2.5-flash-lite"
    llm_model_flash: str = "gemini-2.5-flash"
    llm_model_pro: str = "gemini-2.5-pro"
    llm_embedding_model: str = "text-embedding-004"

    llm_max_output_tokens: int = 2048
    llm_request_timeout_seconds: float = 60.0
    llm_cache_ttl_seconds: int = 3600

    redis_url: str = "redis://redis:6379/0"

    search_provider: str = "tavily"
    search_api_key: str = ""
    search_max_results: int = 5
    search_timeout_seconds: float = 15.0

    fetch_page_timeout_seconds: float = 15.0
    fetch_page_max_bytes: int = 200_000

    file_storage_path: str = "/app/storage"
    max_upload_size_mb: int = 20
    pdf_extract_max_chars: int = 120_000

    @field_validator("database_url", mode="after")
    @classmethod
    def _force_asyncpg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
