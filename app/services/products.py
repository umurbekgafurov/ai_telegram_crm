"""Product business logic (tenant-aware).

No Telegram imports here. Used by bot handlers and (future) FastAPI.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html import escape

from app.database.models import Product
from app.database.repositories.products import ProductRepository

# Limits matching DB schema: NUMERIC(12,2) and 32-bit INT
MAX_PRICE = Decimal("9999999999.99")
MAX_STOCK = 2_147_483_647


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_price(raw: str) -> Decimal:
    """Parse and validate a price. Raises ValueError on invalid input."""
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
    if price > MAX_PRICE:
        raise ValueError("Narx juda katta")
    if price.as_tuple().exponent < -2:
        raise ValueError("Narx 2 xonadan ortiq kasr bo\u2019lishi mumkin emas")
    return price


def validate_stock(raw: str) -> int:
    """Parse and validate a stock quantity. Raises ValueError on invalid input."""
    normalized = (raw or "").strip()
    if not normalized:
        raise ValueError("Miqdor bo\u2019sh bo\u2019lishi mumkin emas")
    if not re.fullmatch(r"[0-9]+", normalized):
        raise ValueError("Miqdor butun son bo\u2019lishi kerak")
    stock = int(normalized)
    if stock > MAX_STOCK:
        raise ValueError("Miqdor juda katta")
    return stock


# --------------------------------------------------------------------------
# SKU uniqueness (pre-check; DB composite constraint is authoritative)
# --------------------------------------------------------------------------


async def validate_sku_unique(
    repo: ProductRepository, tenant_id: int, sku: str
) -> bool:
    """Return True if sku is available within the tenant."""
    existing = await repo.get_by_sku(tenant_id=tenant_id, sku=sku)
    return existing is None


# --------------------------------------------------------------------------
# Creation / listing
# --------------------------------------------------------------------------


async def create_product(
    repo: ProductRepository,
    *,
    tenant_id: int,
    name: str,
    sku: str,
    price: Decimal,
    stock_quantity: int,
) -> Product:
    """Create a product scoped to tenant_id. Does NOT commit."""
    return await repo.create(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        price=price,
        stock_quantity=stock_quantity,
    )


async def list_active_products(
    repo: ProductRepository,
    *,
    tenant_id: int,
    page: int,
    page_size: int,
) -> list[Product]:
    """Return one page of active products for the tenant, newest first."""
    offset = page * page_size
    return await repo.list_active(
        tenant_id=tenant_id, limit=page_size, offset=offset
    )


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------


EMPTY_PAGE_TEXT = "Hozircha faol mahsulotlar yo\u2019q."


def format_products_page(products: list[Product], page: int) -> str:
    """Render a page of products (HTML parse mode, escaped)."""
    if not products and page == 0:
        return EMPTY_PAGE_TEXT
    lines = [f"\U0001F4CB Mahsulotlar (sahifa {page + 1}):\n"]
    for p in products:
        lines.append(
            f"\u2022 {escape(p.name)} \u2014 {p.price} so\u2019m "
            f"(qoldiq: {p.stock_quantity}) [{escape(p.sku)}]"
        )
    return "\n".join(lines)
