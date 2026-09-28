"""Product management handlers: FSM 'Add product' flow and paginated listing."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from html import escape

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


# --------------------------------------------------------------------------
# Entry point: open the products menu (ADMIN ONLY)
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

    existing = await repo.get_by_sku(sku)
    if existing is not None:
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
    raw = (message.text or "").strip().replace(",", ".")
    try:
        price = Decimal(raw)
    except (InvalidOperation, ValueError):
        await message.answer("Narx noto\u2019g\u2019ri formatda. Raqam kiriting (masalan: 150000.00):")
        return

    if price < 0:
        await message.answer("Narx manfiy bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return

    await state.update_data(price=str(price))
    await state.set_state(ProductForm.stock)
    await message.answer("Ombordagi miqdorni kiriting (butun son):")


@router.message(ProductForm.stock)
async def process_stock(message: Message, state: FSMContext) -> None:
    """Step 4: collect and validate stock quantity, then show confirmation."""
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
    data = await state.get_data()

    try:
        existing = await repo.get_by_sku(data["sku"])
        if existing is not None:
            if callback.message is not None:
                await callback.message.answer(
                    "Kechirasiz, bu SKU boshqa mahsulot tomonidan band qilindi. "
                    "Jarayon bekor qilindi."
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
# List products (paginated, ADMIN ONLY)
# --------------------------------------------------------------------------


async def _render_products_page(repo: ProductRepository, page: int) -> tuple[str, int]:
    """Build the text body for a page of products."""
    offset = page * PAGE_SIZE
    products = await repo.list_active(limit=PAGE_SIZE, offset=offset)

    if not products and page == 0:
        return "Hozircha faol mahsulotlar yo\u2019q.", 0

    lines = [f"\U0001F4CB Mahsulotlar (sahifa {page + 1}):\n"]
    for p in products:
        lines.append(
            f"\u2022 {escape(p.name)} \u2014 {p.price} so\u2019m "
            f"(qoldiq: {p.stock_quantity}) [{escape(p.sku)}]"
        )

    return "\n".join(lines), len(products)


@router.callback_query(F.data == CB_PRODUCT_LIST)
@admin_only
async def list_products(
    callback: CallbackQuery, repo: ProductRepository, session: AsyncSession
) -> None:
    """Show the first page of the product list."""
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
    text, count = await _render_products_page(repo, page=page)
    kb = products_pagination_kb(page=page, has_next=count == PAGE_SIZE, has_prev=page > 0)

    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == CB_PRODUCT_SEARCH)
@admin_only
async def search_products_stub(callback: CallbackQuery, session: AsyncSession) -> None:
    """Placeholder for search (out of scope for M1)."""
    await callback.answer("Qidiruv funksiyasi tez orada qo\u2019shiladi.", show_alert=True)


# --------------------------------------------------------------------------
# Navigation
# --------------------------------------------------------------------------


@router.callback_query(F.data == CB_PRODUCT_MENU)
@admin_only
async def back_to_products_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """Return to the main Products inline menu."""
    if callback.message is not None:
        await callback.message.edit_text(
            "Mahsulotlar bo\u2019limi:",
            reply_markup=product_menu(),
        )
    await callback.answer()


@router.callback_query(F.data == CB_HOME)
async def back_to_home(callback: CallbackQuery, state: FSMContext) -> None:
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
# FSM cancel (must be the last handler in this router)
# --------------------------------------------------------------------------


@router.message(Command("cancel"))
async def cancel_any_fsm(message: Message, state: FSMContext) -> None:
    """Cancel any active FSM flow (works in any state)."""
    current = await state.get_state()
    if current is None:
        await message.answer("Hozircha faol jarayon yo\u2019q.")
        return

    await state.clear()
    await message.answer(
        "\u274C Jarayon bekor qilindi.",
        reply_markup=main_admin_menu(),
    )
