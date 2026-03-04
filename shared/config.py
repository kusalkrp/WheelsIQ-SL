"""
Prime Wheels SL — Shared configuration using pydantic-settings.
All env vars are loaded from .env automatically.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ── App ──
    app_name: str = "Prime Wheels SL"
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://pw_user:changeme_in_production@localhost:5432/primewheels"
    sync_database_url: str = "postgresql://pw_user:changeme_in_production@localhost:5432/primewheels"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Qdrant ──
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "vehicles"

    # ── Gemini ──
    gemini_api_key: str = ""
    gemini_flash_model: str = "gemini-2.5-flash"

    # ── Embeddings ──
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 3072  # native output dim of gemini-embedding-001

    # ── Scraper ──
    scrape_delay_min: float = 3.0
    scrape_delay_max: float = 8.0
    scrape_max_pages: int = 500
    scrape_categories: list[str] = [
        "cars", "suvs", "vans", "motorcycles",
        "lorries", "three-wheels", "pickups", "heavy-duties",
    ]

    # ── Cache ──
    cache_ttl_seconds: int = 86400  # 24 hours
    semantic_cache_threshold: float = 0.92

    # ── LangFuse ──
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
