"""Pytest configuration.

Loads .env, sets required env vars BEFORE importing app modules,
and provides a real-DB async engine with NullPool.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Load .env manually BEFORE any app import ---
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        os.environ.setdefault(key, value)

# --- Defaults required by app.config at import time ---
os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-FOR-PYTEST")
os.environ.setdefault("ADMIN_IDS", "615532128")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DEV_MODE", "false")
os.environ.setdefault("DEFAULT_TENANT_NAME", "Default Shop")
os.environ.setdefault("DEFAULT_TENANT_SLUG", "default")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402


def _test_db_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def test_engine():
    """Real Postgres engine with NullPool (avoids asyncpg loop errors)."""
    url = _test_db_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — skipping real DB test")

    engine = create_async_engine(url, poolclass=NullPool, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )