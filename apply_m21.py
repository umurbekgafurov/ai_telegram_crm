"""M2.1 — Service Layer Extraction. Run: python apply_m21.py"""

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
FILES: dict[str, str] = {}


# ==========================================================================
# app/services/products.py
# ==========================================================================
FILES["app/services/products.py"] = r'''"""Product business logic.

Used by bot handlers and (future) FastAPI. No Telegram imports here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape

from app.database.models import Product
from app.database.repositories.products import ProductRepository


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_price(raw: str) -> Decimal:
    """Parse and validate a price from user input.

    Accepts "15000", "15000.50", "15000,50".
    Rejects empty, non-numeric, and negative values.

    Raises:
        ValueError: on invalid input.
    """
    normalized = (raw or "").strip().replace(",", ".")
    if not normalized:
        raise ValueError("Narx bo\u2019sh bo\u2019lishi mumkin emas")
    try:
        price = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Narx noto\u2019g\u2019ri formatda") from exc
    if price < 0:
        raise ValueError("Narx manfiy bo\u2019lishi mumkin emas")
    return price


def validate_stock(raw: str) -> int:
    """Parse and validate a stock quantity from user input.

    Accepts "10", "0". Rejects empty, non-integer, negative.

    Raises:
        ValueError: on invalid input.
    """
    normalized = (raw or "").strip()
    if not normalized:
        raise ValueError("Miqdor bo\u2019sh bo\u2019lishi mumkin emas")
    if not normalized.lstrip("-").isdigit():
        raise ValueError("Miqdor butun son bo\u2019lishi kerak")
    stock = int(normalized)
    if stock < 0:
        raise ValueError("Miqdor manfiy bo\u2019lishi mumkin emas")
    return stock


# --------------------------------------------------------------------------
# SKU uniqueness (pre-check only — DB constraint is authoritative)
# --------------------------------------------------------------------------


async def validate_sku_unique(repo: ProductRepository, sku: str) -> bool:
    """Return True if `sku` is available, False if already taken.

    NOTE: This is a pre-check only. The DB unique constraint on
    products.sku remains the authoritative guard against races.
    """
    existing = await repo.get_by_sku(sku)
    return existing is None


# --------------------------------------------------------------------------
# Product creation / listing
# --------------------------------------------------------------------------


async def create_product(
    repo: ProductRepository,
    *,
    name: str,
    sku: str,
    price: Decimal,
    stock_quantity: int,
) -> Product:
    """Create a Product via the repository.

    Does NOT commit. Transaction ownership stays with the middleware.
    IntegrityError (e.g. duplicate SKU race) propagates to the caller.
    """
    return await repo.create(
        name=name,
        sku=sku,
        price=price,
        stock_quantity=stock_quantity,
    )


async def list_active_products(
    repo: ProductRepository,
    *,
    page: int,
    page_size: int,
) -> list[Product]:
    """Return a single page of active products, newest first."""
    offset = page * page_size
    return await repo.list_active(limit=page_size, offset=offset)


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------


EMPTY_PAGE_TEXT = "Hozircha faol mahsulotlar yo\u2019q."


def format_products_page(products: list[Product], page: int) -> str:
    """Render a page of products for Telegram (HTML parse mode).

    Preserves M2.0's output format and escaping exactly.
    """
    if not products and page == 0:
        return EMPTY_PAGE_TEXT

    lines = [f"\U0001F4CB Mahsulotlar (sahifa {page + 1}):\n"]
    for p in products:
        lines.append(
            f"\u2022 {escape(p.name)} \u2014 {p.price} so\u2019m "
            f"(qoldiq: {p.stock_quantity}) [{escape(p.sku)}]"
        )
    return "\n".join(lines)
'''


# ==========================================================================
# app/services/users.py
# ==========================================================================
FILES["app/services/users.py"] = r'''"""User business logic (upsert + admin promotion)."""

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
'''


# ==========================================================================
# app/handlers/products.py  (thin — calls services)
# ==========================================================================
FILES["app/handlers/products.py"] = r'''"""Product management handlers: thin orchestration over services."""

from __future__ import annotations

import logging

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
from app.services import products as product_service
from app.services.auth import admin_only
from app.states.product import ProductForm

logger = logging.getLogger(__name__)
router = Router(name="products")

PAGE_SIZE = 10


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


@router.message(F.text == "\U0001F4E6 Mahsulotlar")
@admin_only
async def open_products_menu(message: Message, session: AsyncSession) -> None:
    """Show the Products inline menu."""
    await message.answer("Mahsulotlar bo\u2019limi:", reply_markup=product_menu())


# --------------------------------------------------------------------------
# Add product FSM flow
# --------------------------------------------------------------------------


@router.callback_query(F.data == CB_PRODUCT_ADD)
@admin_only
async def start_add_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Begin the 'Add product' FSM flow."""
    await state.set_state(ProductForm.name)
    if callback.message is not None:
        await callback.message.answer("Mahsulot nomini kiriting:")
    await callback.answer()


@router.message(ProductForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Step 1: collect product name."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("Nom bo\u2019sh bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return
    await state.update_data(name=name)
    await state.set_state(ProductForm.sku)
    await message.answer("SKU (unikal kod) kiriting:")


@router.message(ProductForm.sku)
async def process_sku(message: Message, state: FSMContext, repo: ProductRepository) -> None:
    """Step 2: collect and validate SKU uniqueness."""
    sku = (message.text or "").strip()
    if not sku:
        await message.answer("SKU bo\u2019sh bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return

    if not await product_service.validate_sku_unique(repo, sku):
        from html import escape
        await message.answer(
            f"Bu SKU ({escape(sku)}) allaqachon mavjud. Boshqa SKU kiriting:"
        )
        return

    await state.update_data(sku=sku)
    await state.set_state(ProductForm.price)
    await message.answer("Narxni kiriting (masalan: 150000.00):")


@router.message(ProductForm.price)
async def process_price(message: Message, state: FSMContext) -> None:
    """Step 3: collect and validate price."""
    try:
        price = product_service.validate_price(message.text or "")
    except ValueError:
        await message.answer(
            "Narx noto\u2019g\u2019ri formatda. Raqam kiriting (masalan: 150000.00):"
        )
        return
    await state.update_data(price=str(price))
    await state.set_state(ProductForm.stock)
    await message.answer("Ombordagi miqdorni kiriting (butun son):")


@router.message(ProductForm.stock)
async def process_stock(message: Message, state: FSMContext) -> None:
    """Step 4: collect and validate stock, then show confirmation."""
    from html import escape
    try:
        stock = product_service.validate_stock(message.text or "")
    except ValueError:
        await message.answer("Miqdor butun son bo\u2019lishi kerak. Qaytadan kiriting:")
        return

    await state.update_data(stock=stock)
    data = await state.get_data()
    await state.set_state(ProductForm.confirm)

    summary = (
        "Quyidagi mahsulotni saqlashni tasdiqlaysizmi?\n\n"
        f"Nomi: {escape(data['name'])}\n"
        f"SKU: {escape(data['sku'])}\n"
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
    """Persist the product after user confirmation."""
    from decimal import Decimal
    from html import escape

    data = await state.get_data()

    try:
        if not await product_service.validate_sku_unique(repo, data["sku"]):
            if callback.message is not None:
                await callback.message.answer(
                    "Kechirasiz, bu SKU boshqa mahsulot tomonidan band qilindi. "
                    "Jarayon bekor qilindi."
                )
            await state.clear()
            await callback.answer()
            return

        product = await product_service.create_product(
            repo,
            name=data["name"],
            sku=data["sku"],
            price=Decimal(data["price"]),
            stock_quantity=int(data["stock"]),
        )
    except Exception:
        logger.exception("Failed to create product")
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
            f"\u2705 Mahsulot saqlandi: {escape(product.name)} (SKU: {escape(product.sku)})"
        )
    await callback.answer("Saqlandi!")

    logger.info(
        "Product created id=%s sku=%s by admin=%s",
        product.id,
        product.sku,
        callback.from_user.id if callback.from_user else None,
    )


@router.callback_query(ProductForm.confirm, F.data == CB_CONFIRM_NO)
async def cancel_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the 'Add product' flow without saving."""
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Bekor qilindi.")
    await callback.answer()


# --------------------------------------------------------------------------
# List products
# --------------------------------------------------------------------------


@router.callback_query(F.data == CB_PRODUCT_LIST)
@admin_only
async def list_products(
    callback: CallbackQuery, repo: ProductRepository, session: AsyncSession
) -> None:
    """Show the first page of the product list."""
    products = await product_service.list_active_products(
        repo, page=0, page_size=PAGE_SIZE
    )
    text = product_service.format_products_page(products, page=0)
    kb = products_pagination_kb(
        page=0, has_next=len(products) == PAGE_SIZE, has_prev=False
    )
    if callback.message is not None:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_PRODUCT_PAGE_PREFIX))
@admin_only
async def paginate_products(
    callback: CallbackQuery, repo: ProductRepository, session: AsyncSession
) -> None:
    """Navigate to a specific page of the product list."""
    if callback.data is None:
        await callback.answer()
        return

    try:
        page = int(callback.data.removeprefix(CB_PRODUCT_PAGE_PREFIX))
    except ValueError:
        await callback.answer()
        return

    page = max(page, 0)
    products = await product_service.list_active_products(
        repo, page=page, page_size=PAGE_SIZE
    )
    text = product_service.format_products_page(products, page=page)
    kb = products_pagination_kb(
        page=page, has_next=len(products) == PAGE_SIZE, has_prev=page > 0
    )
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == CB_PRODUCT_SEARCH)
@admin_only
async def search_products_stub(callback: CallbackQuery, session: AsyncSession) -> None:
    """Placeholder for search (out of scope for M2.1)."""
    await callback.answer(
        "Qidiruv funksiyasi tez orada qo\u2019shiladi.", show_alert=True
    )


# --------------------------------------------------------------------------
# Navigation
# --------------------------------------------------------------------------


@router.callback_query(F.data == CB_PRODUCT_MENU)
@admin_only
async def back_to_products_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """Return to the main Products inline menu."""
    if callback.message is not None:
        await callback.message.edit_text(
            "Mahsulotlar bo\u2019limi:", reply_markup=product_menu()
        )
    await callback.answer()


@router.callback_query(F.data == CB_HOME)
@admin_only
async def back_to_home(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    """Return to the main reply keyboard menu."""
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


# --------------------------------------------------------------------------
# FSM cancel (must remain last in this router)
# --------------------------------------------------------------------------


@router.message(Command("cancel"))
async def cancel_any_fsm(message: Message, state: FSMContext) -> None:
    """Cancel any active FSM flow."""
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
# app/handlers/start.py  (thin — calls users service)
# ==========================================================================
FILES["app/handlers/start.py"] = r'''"""/start command: upsert the user and show the appropriate menu."""

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
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Handle /start: register/update the user and greet them."""
    if message.from_user is None:
        return

    user = await upsert_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        admin_ids=settings.ADMIN_IDS,
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
'''


# ==========================================================================
# tests/__init__.py
# ==========================================================================
FILES["tests/__init__.py"] = ""


# ==========================================================================
# tests/test_products_service.py
# ==========================================================================
FILES["tests/test_products_service.py"] = r'''"""Unit tests for app.services.products."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import products as svc


# --- validate_price --------------------------------------------------------


def test_validate_price_integer() -> None:
    assert svc.validate_price("15000") == Decimal("15000")


def test_validate_price_decimal() -> None:
    assert svc.validate_price("15000.50") == Decimal("15000.50")


def test_validate_price_comma_decimal() -> None:
    assert svc.validate_price("15000,50") == Decimal("15000.50")


def test_validate_price_empty() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("")


def test_validate_price_whitespace() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("   ")


def test_validate_price_non_numeric() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("abc")


def test_validate_price_negative() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("-100")


# --- validate_stock --------------------------------------------------------


def test_validate_stock_valid() -> None:
    assert svc.validate_stock("10") == 10


def test_validate_stock_zero() -> None:
    assert svc.validate_stock("0") == 0


def test_validate_stock_empty() -> None:
    with pytest.raises(ValueError):
        svc.validate_stock("")


def test_validate_stock_non_numeric() -> None:
    with pytest.raises(ValueError):
        svc.validate_stock("abc")


def test_validate_stock_negative() -> None:
    with pytest.raises(ValueError):
        svc.validate_stock("-1")


def test_validate_stock_decimal() -> None:
    with pytest.raises(ValueError):
        svc.validate_stock("1.5")


# --- validate_sku_unique ---------------------------------------------------


@pytest.mark.asyncio
async def test_validate_sku_unique_available() -> None:
    repo = MagicMock()
    repo.get_by_sku = AsyncMock(return_value=None)
    assert await svc.validate_sku_unique(repo, "NEW-SKU") is True


@pytest.mark.asyncio
async def test_validate_sku_unique_taken() -> None:
    repo = MagicMock()
    repo.get_by_sku = AsyncMock(return_value=object())
    assert await svc.validate_sku_unique(repo, "TAKEN-SKU") is False


# --- create_product --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_calls_repo() -> None:
    repo = MagicMock()
    fake_product = object()
    repo.create = AsyncMock(return_value=fake_product)

    result = await svc.create_product(
        repo,
        name="iPhone 15 Pro",
        sku="IPH15P",
        price=Decimal("15000000.00"),
        stock_quantity=5,
    )

    assert result is fake_product
    repo.create.assert_awaited_once_with(
        name="iPhone 15 Pro",
        sku="IPH15P",
        price=Decimal("15000000.00"),
        stock_quantity=5,
    )


@pytest.mark.asyncio
async def test_create_product_propagates_integrity_error() -> None:
    from sqlalchemy.exc import IntegrityError

    repo = MagicMock()
    repo.create = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))

    with pytest.raises(IntegrityError):
        await svc.create_product(
            repo,
            name="X",
            sku="X",
            price=Decimal("1"),
            stock_quantity=1,
        )


# --- list_active_products --------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_products_pagination() -> None:
    repo = MagicMock()
    repo.list_active = AsyncMock(return_value=[])

    await svc.list_active_products(repo, page=2, page_size=10)

    repo.list_active.assert_awaited_once_with(limit=10, offset=20)


# --- format_products_page --------------------------------------------------


def test_format_empty_page() -> None:
    assert svc.format_products_page([], page=0) == svc.EMPTY_PAGE_TEXT


def _fake_product(name: str, sku: str, price: str, stock: int) -> Any:
    p = MagicMock()
    p.name = name
    p.sku = sku
    p.price = Decimal(price)
    p.stock_quantity = stock
    return p


def test_format_products_page_escapes_html() -> None:
    p = _fake_product("a<b>", "SKU-1", "100", 5)
    text = svc.format_products_page([p], page=0)
    assert "a&lt;b&gt;" in text
    assert "a<b>" not in text


def test_format_products_page_contains_fields() -> None:
    p = _fake_product("iPhone", "IPH-1", "15000000.00", 5)
    text = svc.format_products_page([p], page=0)
    assert "iPhone" in text
    assert "IPH-1" in text
    assert "15000000.00" in text
    assert "5" in text
'''


# ==========================================================================
# tests/test_users_service.py
# ==========================================================================
FILES["tests/test_users_service.py"] = r'''"""Unit tests for app.services.users."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.services import users as svc


def _mock_session_returning(user: User | None) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_upsert_user_creates_new() -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=123,
        username="alice",
        first_name="Alice",
        admin_ids=[],
    )

    assert user.telegram_id == 123
    assert user.role == "customer"
    session.add.assert_called_once()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_user_updates_existing() -> None:
    existing = User(
        telegram_id=123,
        username="old",
        first_name="Old",
        role="customer",
    )
    session = _mock_session_returning(existing)

    user = await svc.upsert_user(
        session,
        telegram_id=123,
        username="new",
        first_name="New",
        admin_ids=[],
    )

    assert user.username == "new"
    assert user.first_name == "New"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_user_promotes_admin() -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=999,
        username="boss",
        first_name="Boss",
        admin_ids=[999],
    )

    assert user.role == "admin"


@pytest.mark.asyncio
async def test_upsert_user_non_admin_stays_customer() -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=555,
        username="u",
        first_name="U",
        admin_ids=[999],
    )

    assert user.role == "customer"


def test_promote_to_admin_does_not_commit() -> None:
    user = User(telegram_id=1, username="x", first_name="X", role="customer")
    # No session passed — this function simply must not require one.
    svc.promote_to_admin_if_needed(user, [1])
    assert user.role == "admin"


def test_promote_to_admin_idempotent() -> None:
    user = User(telegram_id=1, username="x", first_name="X", role="admin")
    svc.promote_to_admin_if_needed(user, [1])
    assert user.role == "admin"
'''


# ==========================================================================
# tests/test_auth.py
# ==========================================================================
FILES["tests/test_auth.py"] = r'''"""Unit tests for app.services.auth (is_admin + @admin_only)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import admin_only, is_admin


# --- is_admin --------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_true_for_admin_role() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="admin")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_true_for_manager_role() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="manager")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_customer() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="customer")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is False


@pytest.mark.asyncio
async def test_is_admin_false_for_unknown_user() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is False


# --- admin_only decorator --------------------------------------------------


@pytest.mark.asyncio
async def test_admin_only_allows_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_is_admin(session, telegram_id):  # noqa: ANN001
        return True

    monkeypatch.setattr("app.services.auth.is_admin", fake_is_admin)

    called: dict[str, bool] = {"hit": False}

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        called["hit"] = True
        return "ok"

    user = MagicMock()
    user.id = 123
    event = MagicMock()
    event.from_user = user

    result = await handler(event, session=MagicMock())
    assert result == "ok"
    assert called["hit"] is True


@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_is_admin(session, telegram_id):  # noqa: ANN001
        return False

    monkeypatch.setattr("app.services.auth.is_admin", fake_is_admin)

    from aiogram.types import CallbackQuery

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        raise AssertionError("handler must not run for non-admin")

    user = MagicMock()
    user.id = 999
    event = MagicMock(spec=CallbackQuery)
    event.from_user = user
    event.answer = AsyncMock()

    result = await handler(event, session=MagicMock())
    assert result is None
    event.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_only_fails_closed_without_session() -> None:
    from aiogram.types import Message

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        raise AssertionError("handler must not run without session")

    event = MagicMock(spec=Message)
    event.from_user = MagicMock(id=123)
    event.answer = AsyncMock()

    result = await handler(event)  # no session kwarg
    assert result is None
    event.answer.assert_awaited()
'''


# ==========================================================================
# pytest configuration — append to pyproject.toml
# ==========================================================================
PYPROJECT_APPEND = '''

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
'''


# ==========================================================================
# Apply
# ==========================================================================
def write_file(rel: str, content: str) -> None:
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"OK: {rel}")


def append_pyproject() -> None:
    p = BASE / "pyproject.toml"
    if not p.exists():
        print("WARN: pyproject.toml not found; skipping pytest config")
        return
    text = p.read_text(encoding="utf-8")
    if "[tool.pytest.ini_options]" in text:
        print("OK: pyproject.toml already has pytest config")
        return
    p.write_text(text + PYPROJECT_APPEND, encoding="utf-8")
    print("OK: pyproject.toml pytest config appended")


def main() -> int:
    print("=" * 70)
    print("M2.1 Service Layer Extraction — writing files")
    print("=" * 70)
    print()

    for rel, content in FILES.items():
        try:
            write_file(rel, content)
        except Exception as e:
            print(f"ERROR writing {rel}: {e}")
        return 1  
  
	append_pyproject()

    print()
    print("=" * 70)
    print("Syntax check:")
    print("=" * 70)
    errors = 0
    for rel in FILES:
        if not rel.endswith(".py"):
            continue
        p = BASE / rel
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"OK compile: {rel}")
        except SyntaxError as e:
            print(f"SYNTAX ERROR in {rel}: {e}")
            errors += 1

    print()
    if errors == 0:
        print("All files written. Next steps:")
        print("  1. pytest -v")
        print("  2. python -B -m app.bot")
        print("  3. git add . && git commit && git push")
    else:
        print(f"{errors} file(s) failed syntax check")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())