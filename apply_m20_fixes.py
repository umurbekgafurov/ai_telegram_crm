"""M2.0 stabilization — apply all Claude M2.0 fixes with UTF-8 encoding.

Run: python apply_m20_fixes.py
"""

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
FILES: dict[str, str] = {}
DELETE: list[str] = []


# ==========================================================================
# app/services/__init__.py
# ==========================================================================
FILES["app/services/__init__.py"] = r'''"""Shared service layer."""
'''


# ==========================================================================
# app/services/auth.py
# ==========================================================================
FILES["app/services/auth.py"] = r'''"""Authorization service + @admin_only decorator."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User

logger = logging.getLogger(__name__)


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
    """Check role from DB (source of truth)."""
    result = await session.execute(
        select(User.role).where(User.telegram_id == telegram_id)
    )
    role = result.scalar_one_or_none()
    return role in ("admin", "manager")


def admin_only(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: gate handler to admin/manager role only.

    The decorated handler MUST declare a `session: AsyncSession` parameter
    (aiogram's DI relies on the wrapped handler's signature via functools.wraps).
    """

    @wraps(handler)
    async def wrapper(event: Any, *args: Any, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        user = getattr(event, "from_user", None)

        if session is None or user is None:
            logger.error("admin_only: missing session or from_user")
            if isinstance(event, CallbackQuery):
                await event.answer("Xatolik yuz berdi.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Xatolik yuz berdi.")
            return None

        if not await is_admin(session, user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Ruxsat yo\u2019q.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Ruxsat yo\u2019q.")
            return None

        return await handler(event, *args, **kwargs)

    return wrapper
'''


# ==========================================================================
# app/config.py
# ==========================================================================
FILES["app/config.py"] = r'''"""Application configuration loaded from environment variables (.env)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )

    BOT_TOKEN: str = Field(..., description="Telegram Bot API token")
    DATABASE_URL: str = Field(..., description="Async SQLAlchemy DSN")
    ADMIN_IDS: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="Telegram user IDs that are granted admin role",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Python logging level")
    DEV_MODE: bool = Field(default=False, description="Dev mode: create tables on startup")

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> list[int]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    return [int(v) for v in json.loads(stripped)]
                except (json.JSONDecodeError, ValueError, TypeError):
                    return []
            return [int(p.strip()) for p in stripped.split(",") if p.strip()]
        if isinstance(value, list):
            return [int(v) for v in value]
        return []

    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got {value!r}")
        return upper


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
'''


# ==========================================================================
# app/database/models.py
# ==========================================================================
FILES["app/database/models.py"] = r'''"""SQLAlchemy 2.0 ORM models: User, Category, Product."""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="customer")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<User id={self.id} telegram_id={self.telegram_id} "
            f"username={self.username!r} role={self.role!r}>"
        )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="category", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} name={self.name!r}>"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("cost_price >= 0", name="ck_products_cost_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    stock_quantity: Mapped[int] = mapped_column(nullable=False, server_default="0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped[Category | None] = relationship("Category", back_populates="products")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Product id={self.id} sku={self.sku!r} name={self.name!r} "
            f"price={self.price} stock={self.stock_quantity} status={self.status!r}>"
        )
'''


# ==========================================================================
# app/middlewares/db.py
# ==========================================================================
FILES["app/middlewares/db.py"] = r'''"""Middleware: injects per-update DB session + repository."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.exc import PendingRollbackError

from app.database.database import async_session_factory
from app.database.repositories.products import ProductRepository

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Opens one AsyncSession per update; commits on success, rolls back on error."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            data["repo"] = ProductRepository(session)
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                logger.exception("Unhandled exception in handler; session rolled back.")
                raise
            else:
                try:
                    await session.commit()
                except PendingRollbackError:
                    logger.exception(
                        "Session was rollback-only at commit; a handler probably "
                        "swallowed an IntegrityError without rollback()."
                    )
                    await session.rollback()
                    raise
                return result
'''


# ==========================================================================
# app/handlers/admin.py
# ==========================================================================
FILES["app/handlers/admin.py"] = r'''"""/admin section: reports, settings (stubs for M1)."""

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
'''


# ==========================================================================
# app/handlers/products.py
# ==========================================================================
FILES["app/handlers/products.py"] = r'''"""Product management handlers: FSM + paginated listing."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.products import ProductRepository
from app.keyboards.admin import (
    CB_CONFIRM_NO,
    CB_CONFIRM_YES,
    CB_HOME,
    CB_PRODUCT_ADD,
    CB_PRODUCT_LIST,
    CB_PRODUCT_MENU,
    CB_PRODUCT_PAGE_PREFIX,
    CB_PRODUCT_SEARCH,
    confirm_kb,
    main_admin_menu,
    product_menu,
    products_pagination_kb,
)
from app.services.auth import admin_only
from app.states.product import ProductForm

logger = logging.getLogger(__name__)
router = Router(name="products")

PAGE_SIZE = 10


@router.message(F.text == "\U0001F4E6 Mahsulotlar")
@admin_only
async def open_products_menu(message: Message, session: AsyncSession) -> None:
    await message.answer("Mahsulotlar bo\u2019limi:", reply_markup=product_menu())


@router.callback_query(F.data == CB_PRODUCT_ADD)
@admin_only
async def start_add_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    await state.set_state(ProductForm.name)
    if callback.message is not None:
        await callback.message.answer("Mahsulot nomini kiriting:")
    await callback.answer()


@router.message(ProductForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Nom bo\u2019sh bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return
    await state.update_data(name=name)
    await state.set_state(ProductForm.sku)
    await message.answer("SKU (unikal kod) kiriting:")


@router.message(ProductForm.sku)
async def process_sku(message: Message, state: FSMContext, repo: ProductRepository) -> None:
    sku = (message.text or "").strip()
    if not sku:
        await message.answer("SKU bo\u2019sh bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return
    existing = await repo.get_by_sku(sku)
    if existing is not None:
        await message.answer(f"Bu SKU ({sku}) allaqachon mavjud. Boshqa SKU kiriting:")
        return
    await state.update_data(sku=sku)
    await state.set_state(ProductForm.price)
    await message.answer("Narxni kiriting (masalan: 150000.00):")


@router.message(ProductForm.price)
async def process_price(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        price = Decimal(raw)
    except (InvalidOperation, ValueError):
        await message.answer("Narx noto\u2019g\u2019ri formatda. Raqam kiriting:")
        return
    if price < 0:
        await message.answer("Narx manfiy bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return
    await state.update_data(price=str(price))
    await state.set_state(ProductForm.stock)
    await message.answer("Ombordagi miqdorni kiriting (butun son):")


@router.message(ProductForm.stock)
async def process_stock(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Miqdor butun son bo\u2019lishi kerak. Qaytadan kiriting:")
        return
    stock = int(raw)
    if stock < 0:
        await message.answer("Miqdor manfiy bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return
    await state.update_data(stock=stock)
    data = await state.get_data()
    await state.set_state(ProductForm.confirm)
    summary = (
        "Quyidagi mahsulotni saqlashni tasdiqlaysizmi?\n\n"
        f"Nomi: {data['name']}\n"
        f"SKU: {data['sku']}\n"
        f"Narx: {data['price']}\n"
        f"Miqdor: {data['stock']}"
    )
    await message.answer(summary, reply_markup=confirm_kb())


@router.callback_query(ProductForm.confirm, F.data == CB_CONFIRM_YES)
@admin_only
async def confirm_add_product(
    callback: CallbackQuery,
    state: FSMContext,
    repo: ProductRepository,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    try:
        existing = await repo.get_by_sku(data["sku"])
        if existing is not None:
            if callback.message is not None:
                await callback.message.answer(
                    "Kechirasiz, bu SKU boshqa mahsulot tomonidan band qilindi."
                )
            await state.clear()
            await callback.answer()
            return
        product = await repo.create(
            name=data["name"],
            sku=data["sku"],
            price=Decimal(data["price"]),
            stock_quantity=int(data["stock"]),
        )
    except Exception:
        logger.exception("Failed to create product")
        # CRITICAL: rollback so the session is not left in a failed state.
        await session.rollback()
        if callback.message is not None:
            await callback.message.answer(
                "Xatolik yuz berdi, mahsulot saqlanmadi. Qaytadan urinib ko\u2019ring."
            )
        await state.clear()
        await callback.answer()
        return
    await state.clear()
    if callback.message is not None:
        await callback.message.answer(
            f"\u2705 Mahsulot saqlandi: {product.name} (SKU: {product.sku})"
        )
    await callback.answer("Saqlandi!")


@router.callback_query(ProductForm.confirm, F.data == CB_CONFIRM_NO)
async def cancel_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Bekor qilindi.")
    await callback.answer()


async def _render_products_page(repo: ProductRepository, page: int) -> tuple[str, int]:
    offset = page * PAGE_SIZE
    products = await repo.list_active(limit=PAGE_SIZE, offset=offset)
    if not products and page == 0:
        return "Hozircha faol mahsulotlar yo\u2019q.", 0
    lines = [f"\U0001F4CB Mahsulotlar (sahifa {page + 1}):\n"]
    for p in products:
        lines.append(
            f"\u2022 {p.name} \u2014 {p.price} so\u2019m "
            f"(qoldiq: {p.stock_quantity}) [{p.sku}]"
        )
    return "\n".join(lines), len(products)


@router.callback_query(F.data == CB_PRODUCT_LIST)
@admin_only
async def list_products(
    callback: CallbackQuery, repo: ProductRepository, session: AsyncSession
) -> None:
    text, count = await _render_products_page(repo, page=0)
    kb = products_pagination_kb(page=0, has_next=count == PAGE_SIZE, has_prev=False)
    if callback.message is not None:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_PRODUCT_PAGE_PREFIX))
@admin_only
async def paginate_products(
    callback: CallbackQuery, repo: ProductRepository, session: AsyncSession
) -> None:
    if callback.data is None:
        await callback.answer()
        return
    try:
        page = int(callback.data.removeprefix(CB_PRODUCT_PAGE_PREFIX))
    except ValueError:
        await callback.answer()
        return
    page = max(page, 0)
    text, count = await _render_products_page(repo, page=page)
    kb = products_pagination_kb(page=page, has_next=count == PAGE_SIZE, has_prev=page > 0)
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == CB_PRODUCT_SEARCH)
@admin_only
async def search_products_stub(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer("Qidiruv funksiyasi tez orada qo\u2019shiladi.", show_alert=True)


@router.callback_query(F.data == CB_PRODUCT_MENU)
@admin_only
async def back_to_products_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is not None:
        await callback.message.edit_text(
            "Mahsulotlar bo\u2019limi:", reply_markup=product_menu()
        )
    await callback.answer()


@router.callback_query(F.data == CB_HOME)
async def back_to_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            await callback.message.edit_text("\U0001F3E0 Bosh menyu")
        await callback.message.answer(
            "\U0001F3E0 <b>Bosh menyu</b>\n\n"
            "Quyidagi bo\u2019limlardan birini tanlang:",
            reply_markup=main_admin_menu(),
        )
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_any_fsm(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Hozircha faol jarayon yo\u2019q.")
        return
    await state.clear()
    await message.answer(
        "\u274C Jarayon bekor qilindi.", reply_markup=main_admin_menu()
    )
'''


# ==========================================================================
# app/bot.py
# ==========================================================================
FILES["app/bot.py"] = r'''"""Bot entrypoint: setup, router registration, startup/shutdown, polling."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

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
    if dev_mode:
        logger.info("DEV_MODE enabled: running init_db() to create tables.")
        await init_db()
    logger.info("Bot startup complete.")


async def on_shutdown() -> None:
    await dispose_engine()
    logger.info("Bot shutdown complete.")


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.LOG_LEVEL)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("Unhandled exception", exc_info=event.exception)
        try:
            update = event.update
            if update.message is not None:
                await update.message.answer(
                    "Xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko\u2019ring."
                )
            elif update.callback_query is not None:
                await update.callback_query.answer(
                    "Xatolik yuz berdi.", show_alert=True
                )
        except Exception:
            logger.exception("Failed to notify user about error")

    dispatcher.update.middleware(DatabaseMiddleware())

    dispatcher.include_router(start.router)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(products.router)

    await on_startup(settings.DEV_MODE)

    try:
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
'''


# ==========================================================================
# alembic/versions/b7c8d9e0f1a2_m20_timestamptz.py
# ==========================================================================
FILES["alembic/versions/b7c8d9e0f1a2_m20_timestamptz.py"] = r'''"""M2.0: TIMESTAMP -> TIMESTAMPTZ on timestamp columns + index on products.category_id.

Revision ID: b7c8d9e0f1a2
Revises: 852baa98043b
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: str | None = '852baa98043b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing naive values were written by func.now() under Supabase's
    # default UTC server timezone. AT TIME ZONE 'UTC' reinterprets them
    # explicitly as UTC before attaching the zone, so no instant shifts.
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE categories "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN updated_at TYPE TIMESTAMPTZ "
        "USING updated_at AT TIME ZONE 'UTC'"
    )
    op.create_index(
        op.f('ix_products_category_id'), 'products', ['category_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN updated_at TYPE TIMESTAMP "
        "USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE categories "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
'''


# ==========================================================================
# .gitignore
# ==========================================================================
FILES[".gitignore"] = r'''# Environment (SECRETS — never commit!)
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/
.eggs/

# Virtual environment
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
desktop.ini

# Logs
*.log
logs/

# Caches
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# NOTE: poetry.lock IS tracked (reproducible builds).
'''


# ==========================================================================
# Files to delete
# ==========================================================================
DELETE = [
    "app/handlers/admins.py",
    "app/handlers/New Text Document.txt",
    "app/keyboards/New Text Document.cmd",
]


# ==========================================================================
# Apply
# ==========================================================================
def write_file(rel_path: str, content: str) -> None:
    p = BASE / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"OK: {rel_path}")


def delete_file(rel_path: str) -> None:
    p = BASE / rel_path
    if p.exists():
        p.unlink()
        print(f"DELETED: {rel_path}")
    else:
        print(f"SKIP (not found): {rel_path}")


def main() -> int:
    print("=" * 70)
    print("M2.0 Stabilization — writing files with UTF-8 (no BOM)")
    print("=" * 70)
    print()

    for rel_path, content in FILES.items():
        try:
            write_file(rel_path, content)
        except Exception as e:
            print(f"ERROR writing {rel_path}: {e}")
            return 1

    print()
    print("Deleting dead/duplicate files:")
    for rel_path in DELETE:
        try:
            delete_file(rel_path)
        except Exception as e:
            print(f"ERROR deleting {rel_path}: {e}")

    print()
    print("=" * 70)
    print("Syntax check:")
    print("=" * 70)
    errors = 0
    for rel_path in FILES:
        if not rel_path.endswith(".py"):
            continue
        p = BASE / rel_path
        try:
            source = p.read_text(encoding="utf-8")
            compile(source, str(p), "exec")
            print(f"OK compile: {rel_path}")
        except SyntaxError as e:
            print(f"SYNTAX ERROR in {rel_path}: {e}")
            errors += 1

    print()
    if errors == 0:
        print("All good. Next steps:")
        print("  1. alembic upgrade head")
        print("  2. python -B -m app.bot")
        print("  3. git add . && git commit && git push")
    else:
        print(f"{errors} file(s) have syntax errors — fix before running.")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())