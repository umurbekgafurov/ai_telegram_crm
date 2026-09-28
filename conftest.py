"""Pytest configuration for M2.2.1+ tests.

Sets required env vars BEFORE any app import so that
get_settings() (called at import time in config.py, database.py,
handlers/start.py) can construct a Settings object.

Also provides a real-DB async engine with NullPool to avoid
event-loop issues in pytest-asyncio.
"""

# conftest.py
import os
from pathlib import Path

# .env'ni o'qish
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-FOR-PYTEST")
os.environ.setdefault("ADMIN_IDS", "615532128")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DEV_MODE", "false")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402


@pytest_asyncio.fixture
async def test_engine():
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL not set")
    
    engine = create_async_engine(test_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )