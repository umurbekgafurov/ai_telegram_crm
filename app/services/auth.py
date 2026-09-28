"""Authorization service + @admin_only decorator."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User

logger = logging.getLogger(__name__)


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    """Check role from DB (source of truth)."""
    result = await session.execute(
        select(User.role).where(User.telegram_id == telegram_id)
    )
    role = result.scalar_one_or_none()
    return role in ("admin", "manager")


def admin_only(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: gate handler to admin/manager role only.

    The decorated handler MUST declare a `session: AsyncSession` parameter
    (aiogram's DI relies on the wrapped handler's signature via functools.wraps).
    """

    @wraps(handler)
    async def wrapper(event: Any, *args: Any, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        user = getattr(event, "from_user", None)

        if session is None or user is None:
            logger.error("admin_only: missing session or from_user")
            if isinstance(event, CallbackQuery):
                await event.answer("Xatolik yuz berdi.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Xatolik yuz berdi.")
            return None

        if not await is_admin(session, user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Ruxsat yo\u2019q.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Ruxsat yo\u2019q.")
            return None

        return await handler(event, *args, **kwargs)

    return wrapper
