"""Product business logic.

Used by bot handlers and (future) FastAPI. No Telegram imports here.
"""

from __future__ import annotations

import re
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
    if not price.is_finite():
        raise ValueError("Narx noto\u2019g\u2019ri formatda")
    if price < 0:
        raise ValueError("Narx manfiy bo\u2019lishi mumkin emas")
    if price > Decimal("9999999999.99"):
        raise ValueError("Narx juda katta")
    if price.as_tuple().exponent < -2:
        raise ValueError("Narx 2 xonadan ortiq kasr bo\u2019lishi mumkin emas")
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
    if not re.fullmatch(r"[0-9]+", normalized):
        raise ValueError("Miqdor butun son bo\u2019lishi kerak")
    stock = int(normalized)
    if stock > 2_147_483_647:
        raise ValueError("Miqdor juda katta")
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
