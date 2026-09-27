"""Reply and inline keyboards used in the admin flows."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --- Callback data prefixes (kept centralized to avoid magic strings) ---
CB_PRODUCT_ADD = "product:add"
CB_PRODUCT_LIST = "product:list"
CB_PRODUCT_SEARCH = "product:search"
CB_PRODUCT_MENU = "product:menu"
CB_PRODUCT_PAGE_PREFIX = "product:page:"  # + page number
CB_CONFIRM_YES = "confirm:yes"
CB_CONFIRM_NO = "confirm:no"
CB_HOME = "home"
CB_CANCEL = "cancel"


def main_admin_menu() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown to admins after /start."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001F4E6 Mahsulotlar")],
            [KeyboardButton(text="\U0001F4CA Hisobotlar"), KeyboardButton(text="\u2699\uFE0F Sozlamalar")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def product_menu() -> InlineKeyboardMarkup:
    """Inline menu for the Products section."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\u2795 Qo'shish", callback_data=CB_PRODUCT_ADD)],
            [InlineKeyboardButton(text="\U0001F4CB Ro'yxat", callback_data=CB_PRODUCT_LIST)],
            [InlineKeyboardButton(text="\U0001F50D Qidirish", callback_data=CB_PRODUCT_SEARCH)],
            [InlineKeyboardButton(text="\U0001F3E0 Bosh menyu", callback_data=CB_HOME)],
        ]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    """Yes/No confirmation inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\u2705 Ha", callback_data=CB_CONFIRM_YES),
                InlineKeyboardButton(text="\u274C Yo'q", callback_data=CB_CONFIRM_NO),
            ],
            [
                InlineKeyboardButton(text="\U0001F3E0 Bosh menyu", callback_data=CB_HOME),
            ],
        ]
    )


def products_pagination_kb(
    page: int, has_next: bool, has_prev: bool
) -> InlineKeyboardMarkup:
    """Inline navigation for the paginated product list.

    Always includes a "Bosh menyu" button at the bottom.
    """
    pagination_row: list[InlineKeyboardButton] = []
    if has_prev:
        pagination_row.append(
            InlineKeyboardButton(
                text="\u2B05\uFE0F", callback_data=f"{CB_PRODUCT_PAGE_PREFIX}{page - 1}"
            )
        )
    if has_next:
        pagination_row.append(
            InlineKeyboardButton(
                text="\u27A1\uFE0F", callback_data=f"{CB_PRODUCT_PAGE_PREFIX}{page + 1}"
            )
        )

    rows: list[list[InlineKeyboardButton]] = []
    if pagination_row:
        rows.append(pagination_row)
    rows.append([InlineKeyboardButton(text="\U0001F3E0 Bosh menyu", callback_data=CB_HOME)])

    return InlineKeyboardMarkup(inline_keyboard=rows)
