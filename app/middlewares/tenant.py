"""Middleware: resolve server-side tenant context for each update.

Never trusts tenant_id from callback_data / message text / user input.
Resolution chain:
    telegram_id -> users row -> first active membership (with active tenant)
    -> data["tenant_id"], data["membership_role"], data["db_user"]
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMembership, User

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseMiddleware):
    """Resolves tenant context from the authenticated Telegram user.

    Runs AFTER DatabaseMiddleware (which injects `session`).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")
        user = getattr(event, "from_user", None)

        # Defaults: no tenant context
        data.setdefault("tenant_id", None)
        data.setdefault("membership_role", None)
        data.setdefault("db_user", None)

        if session is None or user is None:
            return await handler(event, data)

        # 1. Resolve the user row
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if db_user is None:
            # User hasn't /start'ed yet; no tenant context
            return await handler(event, data)

        data["db_user"] = db_user

        # 2. Resolve first active membership (with active tenant)
        membership_result = await session.execute(
            select(TenantMembership)
            .where(
                TenantMembership.user_id == db_user.id,
                TenantMembership.is_active.is_(True),
            )
            .order_by(TenantMembership.id)
            .limit(1)
        )
        membership = membership_result.scalar_one_or_none()

        if membership is not None:
            data["tenant_id"] = membership.tenant_id
            data["membership_role"] = membership.role

        return await handler(event, data)
