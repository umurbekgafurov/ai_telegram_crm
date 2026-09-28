"""Application configuration loaded from environment variables (.env)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )

    BOT_TOKEN: str = Field(..., description="Telegram Bot API token")
    DATABASE_URL: str = Field(..., description="Async SQLAlchemy DSN")
    ADMIN_IDS: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="Telegram user IDs that are granted admin role",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Python logging level")
    DEV_MODE: bool = Field(default=False, description="Dev mode: create tables on startup")
    DEFAULT_TENANT_NAME: str = Field(default="Default Shop", description="Default tenant display name")
    DEFAULT_TENANT_SLUG: str = Field(default="default", description="Default tenant slug")

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    return [int(v) for v in json.loads(stripped)]
                except (json.JSONDecodeError, ValueError, TypeError):
                    return []
            return [int(p.strip()) for p in stripped.split(",") if p.strip()]
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
    return Settings()  # type: ignore[call-arg]
