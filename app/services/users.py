"""User business logic (upsert + tenant membership)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.services.memberships import ROLE_ADMIN, ensure_membership
from app.services.tenants import get_or_create_default_tenant

logger = logging.getLogger(__name__)


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    admin_ids: list[int],
    default_tenant_name: str,
    default_tenant_slug: str,
) -> User:
    """Create or update a User, and ensure ADMIN_IDS users have a membership.

    Regular (non-admin) users get a users row only -- no membership.
    This matches the current single-tenant CRM where only admins manage data.
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            role="customer",  # legacy
        )
        session.add(user)
        await session.flush()
        logger.info("New user created: telegram_id=%s", telegram_id)
    else:
        user.username = username
        user.first_name = first_name
        await session.flush()

    if telegram_id in admin_ids:
        tenant = await get_or_create_default_tenant(
            session, name=default_tenant_name, slug=default_tenant_slug
        )
        await ensure_membership(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            role=ROLE_ADMIN,
        )
        if user.role != "admin":
            user.role = "admin"
            await session.flush()

    return user
