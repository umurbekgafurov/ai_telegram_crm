"""User business logic (upsert + admin promotion)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User

logger = logging.getLogger(__name__)


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    admin_ids: list[int],
) -> User:
    """Create or update a User by telegram_id.

    Does NOT commit. Transaction ownership stays with the middleware.
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
            role="customer",
        )
        session.add(user)
        await session.flush()
        logger.info("New user created: telegram_id=%s", telegram_id)
    else:
        user.username = username
        user.first_name = first_name
        await session.flush()

    promote_to_admin_if_needed(user, admin_ids)
    return user


def promote_to_admin_if_needed(user: User, admin_ids: list[int]) -> None:
    """Promote `user` to admin if their telegram_id is in `admin_ids`.

    Does NOT commit. Idempotent.
    """
    if user.telegram_id in admin_ids and user.role != "admin":
        user.role = "admin"
        logger.info("User promoted to admin: telegram_id=%s", user.telegram_id)
