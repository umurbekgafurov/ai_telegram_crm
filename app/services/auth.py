"""Authorization service + @admin_only decorator (tenant-aware)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMembership, User
from app.services.memberships import ADMIN_ROLES

logger = logging.getLogger(__name__)

# Sentinel: distinguishes "membership_role not provided" from "explicitly None"
_UNSET: Any = object()


async def is_admin(
    session: AsyncSession, telegram_id: int, tenant_id: int | None = None
) -> bool:
    """Return True if user is OWNER/ADMIN of the given tenant.

    Authorization is ALWAYS based on tenant_memberships, never users.role.
    If tenant_id is None, matches any active admin membership.
    """
    stmt = (
        select(TenantMembership.role)
        .join(User, User.id == TenantMembership.user_id)
        .where(
            User.telegram_id == telegram_id,
            TenantMembership.is_active.is_(True),
            TenantMembership.role.in_(ADMIN_ROLES),
        )
        .limit(1)
    )
    if tenant_id is not None:
        stmt = stmt.where(TenantMembership.tenant_id == tenant_id)

    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    return role in ADMIN_ROLES


def admin_only(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: gate handler to OWNER/ADMIN of the resolved tenant.

    Resolution:
    - If `membership_role` is present in kwargs (including explicit None),
      it is authoritative: role must be in ADMIN_ROLES.
    - Else fall back to DB lookup via `tenant_id`.

    `membership_role` and `tenant_id` are consumed by the decorator
    and are NOT forwarded to the wrapped handler.
    """

    @wraps(handler)
    async def wrapper(event: Any, *args: Any, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        user = getattr(event, "from_user", None)

        # Sentinel-based detection: distinguishes "missing" from "None"
        membership_role = kwargs.pop("membership_role", _UNSET)
        tenant_id = kwargs.pop("tenant_id", None)

        if session is None or user is None:
            logger.error("admin_only: missing session or from_user")
            await _deny(event)
            return None

        if membership_role is not _UNSET:
            # Explicit role provided (possibly None) -> authoritative
            allowed = membership_role in ADMIN_ROLES
        else:
            # Not provided -> resolve from DB
            allowed = await is_admin(session, user.id, tenant_id)

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
