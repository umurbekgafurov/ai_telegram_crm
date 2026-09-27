"""Async SQLAlchemy engine, session factory and base declarative model."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Single async engine for the whole process.
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

# Session factory. expire_on_commit=False so ORM objects remain usable
# (e.g. for sending in a Telegram message) after the transaction commits.
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session as an async context manager.

    Usage:
        async with get_session() as session:
            ...
    """
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()


async def init_db() -> None:
    """Create all tables from metadata.

    Development-only helper. In production, use Alembic migrations instead.
    """
    # Import models so they are registered on Base.metadata before create_all.
    from app.database import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (init_db, dev mode).")


async def dispose_engine() -> None:
    """Dispose of the engine's connection pool on shutdown."""
    await async_engine.dispose()
    logger.info("Database engine disposed.")
