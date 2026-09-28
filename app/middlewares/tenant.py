"""Middleware: resolve server-side tenant context for each update.

CRITICAL: aiogram 3 injects `event_from_user` into `data`. The `Update`
object does NOT have `.from_user`. We MUST read from `data`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant, TenantMembership, User

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseMiddleware):
    """Resolves tenant context from the authenticated Telegram user.

    Runs AFTER DatabaseMiddleware (which injects `session`).

    Resolution chain:
        data['event_from_user'].id
            -> users row
            -> first active membership in an active tenant
            -> data['tenant_id'], data['membership_role'], data['db_user']
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession | None = data.get("session")

        # CRITICAL: aiogram 3 injects `event_from_user`, not `event.from_user`.
        tg_user = data.get("event_from_user")

        # Defaults
        data.setdefault("tenant_id", None)
        data.setdefault("membership_role", None)
        data.setdefault("db_user", None)

        if session is None or tg_user is None:
            return await handler(event, data)

        # 1. Resolve the user row
        result = await session.execute(
            select(User).where(User.telegram_id == tg_user.id)
        )
        db_user = result.scalar_one_or_none()

        if db_user is None:
            # User hasn't /start'ed yet
            return await handler(event, data)

        data["db_user"] = db_user

        # 2. Resolve first ACTIVE membership in an ACTIVE tenant
        stmt = (
            select(TenantMembership)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                TenantMembership.user_id == db_user.id,
                TenantMembership.is_active.is_(True),
                Tenant.is_active.is_(True),
            )
            .order_by(TenantMembership.id)
            .limit(1)
        )
        membership_result = await session.execute(stmt)
        membership = membership_result.scalar_one_or_none()

        if membership is not None:
            data["tenant_id"] = membership.tenant_id
            data["membership_role"] = membership.role

        return await handler(event, data)
