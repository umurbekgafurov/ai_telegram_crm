"""/admin section: reports, settings (stubs for M1)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import admin_only

logger = logging.getLogger(__name__)
router = Router(name="admin")


@router.message(F.text == "\U0001F4CA Hisobotlar")
@admin_only
async def reports_menu(message: Message, session: AsyncSession) -> None:
    await message.answer(
        "\U0001F4CA <b>Hisobotlar</b>\n\n"
        "Bu bo\u2019lim M7 milestone'da to'liq ishga tushadi:\n"
        "\u2022 Kunlik/haftalik savdo\n"
        "\u2022 Lidlar funnel\n"
        "\u2022 AI xarajatlar\n\n"
        "Hozircha mavjud emas."
    )


@router.message(F.text == "\u2699\uFE0F Sozlamalar")
@admin_only
async def settings_menu(message: Message, session: AsyncSession) -> None:
    await message.answer(
        "\u2699\uFE0F <b>Sozlamalar</b>\n\n"
        "Bu bo\u2019lim M8 milestone'da to'liq ishga tushadi:\n"
        "\u2022 Adminlar boshqaruvi\n"
        "\u2022 AI promptlar\n"
        "\u2022 Integratsiyalar\n\n"
        "Hozircha mavjud emas."
    )
