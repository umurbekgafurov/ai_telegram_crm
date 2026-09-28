"""Product management handlers: thin orchestration over services."""

from __future__ import annotations

import logging
from decimal import Decimal
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


# --------------------------------------------------------------------------
# FSM cancel — registered BEFORE ProductForm handlers
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
async def process_sku(
    message: Message,
    state: FSMContext,
    repo: ProductRepository,
    tenant_id: int | None = None,
) -> None:
    """Step 2: collect and validate SKU uniqueness within the tenant."""
    sku = (message.text or "").strip()
    if not sku:
        await message.answer("SKU bo\u2019sh bo\u2019lishi mumkin emas. Qaytadan kiriting:")
        return

    if tenant_id is None:
        await message.answer("Tenant topilmadi. Qaytadan /start qiling.")
        await state.clear()
        return

    if not await product_service.validate_sku_unique(repo, tenant_id, sku):
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
    except ValueError as exc:
        await message.answer(escape(str(exc)) + ". Qaytadan kiriting:")
        return
    await state.update_data(price=str(price))
    await state.set_state(ProductForm.stock)
    await message.answer("Ombordagi miqdorni kiriting (butun son):")


@router.message(ProductForm.stock)
async def process_stock(message: Message, state: FSMContext) -> None:
    """Step 4: collect and validate stock, then show confirmation."""
    try:
        stock = product_service.validate_stock(message.text or "")
    except ValueError as exc:
        await message.answer(escape(str(exc)) + ". Qaytadan kiriting:")
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
    tenant_id: int | None = None,
) -> None:
    """Persist the product after user confirmation."""
    if tenant_id is None:
        if callback.message is not None:
            await callback.message.answer("Tenant topilmadi. Qaytadan /start qiling.")
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()

    try:
        if not await product_service.validate_sku_unique(repo, tenant_id, data["sku"]):
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
            tenant_id=tenant_id,
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
        "Product created id=%s tenant_id=%s sku=%s by admin=%s",
        product.id,
        product.tenant_id,
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
# List products (tenant-scoped)
# --------------------------------------------------------------------------


@router.callback_query(F.data == CB_PRODUCT_LIST)
@admin_only
async def list_products(
    callback: CallbackQuery,
    repo: ProductRepository,
    session: AsyncSession,
    tenant_id: int | None = None,
) -> None:
    """Show the first page of the product list."""
    if tenant_id is None:
        if callback.message is not None:
            await callback.message.answer("Tenant topilmadi. Qaytadan /start qiling.")
        await callback.answer()
        return

    products = await product_service.list_active_products(
        repo, tenant_id=tenant_id, page=0, page_size=PAGE_SIZE
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
    callback: CallbackQuery,
    repo: ProductRepository,
    session: AsyncSession,
    tenant_id: int | None = None,
) -> None:
    """Navigate to a specific page of the product list."""
    if callback.data is None:
        await callback.answer()
        return

    if tenant_id is None:
        await callback.answer("Tenant topilmadi.", show_alert=True)
        return

    try:
        page = int(callback.data.removeprefix(CB_PRODUCT_PAGE_PREFIX))
    except ValueError:
        await callback.answer()
        return

    page = max(page, 0)
    products = await product_service.list_active_products(
        repo, tenant_id=tenant_id, page=page, page_size=PAGE_SIZE
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
    """Placeholder for search (out of scope for M2.2)."""
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
