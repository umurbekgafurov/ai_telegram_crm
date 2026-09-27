"""/admin section: reports, settings, and stub handlers for M1."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app.config import get_settings

logger = logging.getLogger(__name__)
router = Router(name="admin")

settings = get_settings()


@router.message(F.text == "📊 Hisobotlar")
async def reports_menu(message: Message) -> None:
    """Reports section — M7'da to'liq ishlaydi."""
    if message.from_user is None or message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("Ruxsat yo'q.")
        return
    await message.answer(
        "📊 <b>Hisobotlar</b>\n\n"
        "Bu bo'lim M7 milestone'da to'liq ishga tushadi:\n"
        "• Kunlik/haftalik savdo\n"
        "• Lidlar funnel\n"
        "• AI xarajatlar\n\n"
        "Hozircha mavjud emas."
    )


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message) -> None:
    """Settings section — M8'da to'liq ishlaydi."""
    if message.from_user is None or message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("Ruxsat yo'q.")
        return
    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bu bo'lim M8 milestone'da to'liq ishga tushadi:\n"
        "• Adminlar boshqaruvi\n"
        "• AI promptlar\n"
        "• Integratsiyalar\n\n"
        "Hozircha mavjud emas."
    )