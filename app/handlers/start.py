"""/start command: upsert the user and show the appropriate menu."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import User
from app.keyboards.admin import main_admin_menu

logger = logging.getLogger(__name__)
router = Router(name="start")

settings = get_settings()


async def _upsert_user(session: AsyncSession, telegram_id: int, username: str | None,
                        first_name: str | None) -> User:
    """Create the user if new, otherwise update mutable profile fields.

    Promotes the user to 'admin' role if their telegram_id is in ADMIN_IDS.
    """
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    is_admin = telegram_id in settings.ADMIN_IDS

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            role="admin" if is_admin else "customer",
        )
        session.add(user)
        await session.flush()
        logger.info("New user created: telegram_id=%s role=%s", telegram_id, user.role)
    else:
        user.username = username
        user.first_name = first_name
        if is_admin and user.role != "admin":
            user.role = "admin"
            logger.info("User promoted to admin: telegram_id=%s", telegram_id)
        await session.flush()

    return user


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Handle /start: register/update the user and greet them."""
    if message.from_user is None:
        return

    user = await _upsert_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    if user.role in ("admin", "manager"):
        await message.answer(
            f"Xush kelibsiz, {user.first_name or 'admin'}! Boshqaruv paneli tayyor.",
            reply_markup=main_admin_menu(),
        )
    else:
        await message.answer(
            f"Assalomu alaykum, {user.first_name or 'mijoz'}! "
            "Bizning botimizga xush kelibsiz. Mahsulotlarimiz bilan tanishishingiz mumkin."
        )
