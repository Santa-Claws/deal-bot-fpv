"""
Application configuration using pydantic-settings.

pydantic-settings automatically reads values from environment variables
and .env files. The field names map directly to env var names.

Example: DATABASE_URL env var → settings.database_url
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central config object. Values come from environment variables
    (set in docker-compose.yml or a local .env file).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL and database_url both work
    )

    # ── Database ──────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://fpvdeals:changeme@localhost:5432/fpvdeals",
        description="Full PostgreSQL connection string with asyncpg driver",
    )

    # ── Redis / Celery ─────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for Celery task broker",
    )

    # ── Meilisearch ────────────────────────────────────
    meili_host: str = Field(
        default="http://localhost:7700",
        description="Meilisearch server URL",
    )
    meili_master_key: str = Field(
        default="changeme",
        description="Meilisearch admin key (set this to something strong in prod)",
    )

    # ── AI ────────────────────────────────────────────
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama API URL for local LLM inference",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key - optional fallback if Ollama is unavailable",
    )

    # ── Notifications ─────────────────────────────────
    discord_webhook_url: Optional[str] = Field(
        default=None,
        description="Discord webhook URL for deal alerts",
    )

    # ── Scraping ──────────────────────────────────────
    scrape_interval_hours: int = Field(
        default=6,
        description="How often to re-scrape each store",
    )
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="Browser user agent string to use during scraping",
    )

    # ── Logging ───────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )


def load_ai_config() -> dict:
    """
    Load AI model configuration from config/ai.yaml.

    This is separate from the main Settings so that model selection
    can be changed without restarting containers.
    """
    config_path = Path("/app/config/ai.yaml")
    if not config_path.exists():
        # Fallback defaults if config file isn't mounted
        return {
            "provider": "ollama",
            "ollama": {"model": "mistral:7b", "host": "http://ollama:11434"},
            "openai": {"model": "gpt-3.5-turbo"},
        }
    with open(config_path) as f:
        return yaml.safe_load(f)


# Global singleton - import this wherever you need config
# Usage: from app.config import settings
settings = Settings()
