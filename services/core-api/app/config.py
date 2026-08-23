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
