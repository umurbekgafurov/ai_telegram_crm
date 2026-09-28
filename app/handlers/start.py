"""/start command: upsert the user and show the appropriate menu."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.keyboards.admin import main_admin_menu
from app.services.users import upsert_user

logger = logging.getLogger(__name__)
router = Router(name="start")

settings = get_settings()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    membership_role: str | None = None,
) -> None:
    """Handle /start: register/update the user and greet them."""
    if message.from_user is None:
        return

    user = await upsert_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        admin_ids=settings.ADMIN_IDS,
        default_tenant_name=settings.DEFAULT_TENANT_NAME,
        default_tenant_slug=settings.DEFAULT_TENANT_SLUG,
    )

    # membership_role is injected by TenantMiddleware on the NEXT update,
    # so for the first /start we resolve directly from the freshly-created
    # membership (or fall back to users.role for legacy users).
    is_admin_user = (
        membership_role in ("OWNER", "ADMIN")
        or message.from_user.id in settings.ADMIN_IDS
    )

    if is_admin_user:
        await message.answer(
            f"Xush kelibsiz, {user.first_name or 'admin'}! Boshqaruv paneli tayyor.",
            reply_markup=main_admin_menu(),
        )
    else:
        await message.answer(
            f"Assalomu alaykum, {user.first_name or 'mijoz'}! "
            "Bizning botimizga xush kelibsiz. Mahsulotlarimiz bilan tanishishingiz mumkin."
        )
