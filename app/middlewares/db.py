"""Middleware: injects per-update DB session + repository."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.database import async_session_factory
from app.database.repositories.products import ProductRepository

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Opens one AsyncSession per update; commits on success, rolls back on error."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            data["repo"] = ProductRepository(session)
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                logger.exception("Unhandled exception in handler; session rolled back.")
                raise
            else:
                try:
                    await session.commit()
                except Exception:
                    logger.exception("Commit failed; rolling back.")
                    await session.rollback()
                    raise
                return result
