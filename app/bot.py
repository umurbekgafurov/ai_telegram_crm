"""Bot entrypoint: setup, router registration, startup/shutdown, polling."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.database.database import dispose_engine, init_db
from app.handlers import admin, products, start
from app.middlewares.db import DatabaseMiddleware

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


async def on_startup(dev_mode: bool) -> None:
    """Run startup tasks."""
    if dev_mode:
        logger.info("DEV_MODE enabled: running init_db() to create tables.")
        await init_db()
    logger.info("Bot startup complete.")


async def on_shutdown() -> None:
    """Run graceful shutdown tasks."""
    await dispose_engine()
    logger.info("Bot shutdown complete.")


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.LOG_LEVEL)

    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    # Middlewares — DB session/repo injected for every update (messages + callbacks).
    dispatcher.update.middleware(DatabaseMiddleware())

    # Routers — ORDER MATTERS:
    #   admin first (its text handlers must not be shadowed by products)
    #   products second (handles 📦 Mahsulotlar and FSM)
    #   start last (only /start)
    dispatcher.include_router(start.router)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(products.router)

    await on_startup(dev_mode)

    try:
        # Drop any pending updates accumulated while the bot was offline.
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    except Exception:
        logger.exception("Fatal error during polling.")
        raise
    finally:
        await on_shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")