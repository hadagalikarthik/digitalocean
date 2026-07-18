from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "url-shortener"
    environment: str = "development"
    base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+psycopg2://shortener:shortener@localhost:5432/shortener"
    redis_url: str = "redis://localhost:6379/0"
    short_code_length: int = 7
    cache_ttl_seconds: int = 300
    idempotency_ttl_seconds: int = 86400
    idempotency_lock_wait_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
