FILES["app/services/auth.py"] = '''"""Authorization service + @admin_only decorator (tenant-aware).""" 

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMembership
from app.services.memberships import ADMIN_ROLES

logger = logging.getLogger(__name__)


async def is_admin(
    session: AsyncSession, telegram_id: int, tenant_id: int | None = None
) -> bool:
    """Return True if user is admin of the given tenant.

    If tenant_id is None, resolves the user's first active tenant membership
    and checks its role. Authorization is ALWAYS based on tenant_memberships,
    never on users.role.
    """
    if tenant_id is None:
        # Resolve user's first active admin membership
        result = await session.execute(
            select(TenantMembership.role)
            .join(
                "users",
                "users.id = tenant_memberships.user_id",
            )
            .where(
                "users.telegram_id = :tid",
                TenantMembership.is_active.is_(True),
                TenantMembership.role.in_(ADMIN_ROLES),
            )
            .limit(1),
            {"tid": telegram_id},
        )
        role = result.scalar_one_or_none()
        return role in ADMIN_ROLES

    result = await session.execute(
        select(TenantMembership.role)
        .join("users", "users.id = tenant_memberships.user_id")
        .where(
            "users.telegram_id = :tid",
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
        ),
        {"tid": telegram_id},
    )
    role = result.scalar_one_or_none()
    return role in ADMIN_ROLES


def admin_only(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: gate handler to OWNER/ADMIN of the resolved tenant.

    Requires `session` in kwargs (via DatabaseMiddleware) and either
    `tenant_id`/`membership_role` in kwargs (via TenantMiddleware) or
    it will resolve from DB.
    """

    @wraps(handler)
    async def wrapper(event: Any, *args: Any, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        user = getattr(event, "from_user", None)
        membership_role = kwargs.get("membership_role")

        if session is None or user is None:
            logger.error("admin_only: missing session or from_user")
            await _deny(event)
            return None

        if membership_role is not None:
            allowed = membership_role in ADMIN_ROLES
        else:
            allowed = await is_admin(session, user.id, kwargs.get("tenant_id"))

        if not allowed:
            await _deny(event)
            return None

        return await handler(event, *args, **kwargs)

    return wrapper


async def _deny(event: Any) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer("Ruxsat yo\u2019q.", show_alert=True)
    elif isinstance(event, Message):
        await event.answer("Ruxsat yo\u2019q.")
