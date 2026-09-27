"""Application configuration loaded from environment variables (.env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    All values are read from environment variables / a local .env file.
    Never hardcode secrets here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    BOT_TOKEN: str = Field(..., description="Telegram Bot API token")
    DATABASE_URL: str = Field(
        ...,
        description="Async SQLAlchemy DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    ADMIN_IDS: list[int] = Field(
        default_factory=list,
        description="Telegram user IDs that are granted admin role on /start",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Python logging level")

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        """Allow ADMIN_IDS to be provided as a comma-separated string in .env."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [int(part.strip()) for part in stripped.split(",") if part.strip()]
        if isinstance(value, list):
            return [int(v) for v in value]
        return []

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got {value!r}")
        return upper


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Cached so the .env file is parsed only once per process.
    """
    return Settings()  # type: ignore[call-arg]
