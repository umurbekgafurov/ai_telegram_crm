"""Unit tests for app.services.products (tenant-aware)."""

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


def test_validate_price_nan() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("NaN")


def test_validate_price_infinity() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("Infinity")


def test_validate_price_too_large() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("10000000000")


def test_validate_price_too_many_decimals() -> None:
    with pytest.raises(ValueError):
        svc.validate_price("10.999")


def test_validate_price_max_boundary() -> None:
    assert svc.validate_price("9999999999.99") == Decimal("9999999999.99")


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


def test_validate_stock_too_large() -> None:
    with pytest.raises(ValueError):
        svc.validate_stock("2147483648")


def test_validate_stock_max_boundary() -> None:
    assert svc.validate_stock("2147483647") == 2147483647


# --- validate_sku_unique (tenant-scoped) -----------------------------------


@pytest.mark.asyncio
async def test_validate_sku_unique_available() -> None:
    repo = MagicMock()
    repo.get_by_sku = AsyncMock(return_value=None)
    assert await svc.validate_sku_unique(repo, 1, "NEW-SKU") is True
    repo.get_by_sku.assert_awaited_once_with(tenant_id=1, sku="NEW-SKU")


@pytest.mark.asyncio
async def test_validate_sku_unique_taken() -> None:
    repo = MagicMock()
    repo.get_by_sku = AsyncMock(return_value=object())
    assert await svc.validate_sku_unique(repo, 1, "TAKEN-SKU") is False


# --- create_product --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_calls_repo() -> None:
    repo = MagicMock()
    fake_product = object()
    repo.create = AsyncMock(return_value=fake_product)

    result = await svc.create_product(
        repo,
        tenant_id=42,
        name="iPhone 15 Pro",
        sku="IPH15P",
        price=Decimal("15000000.00"),
        stock_quantity=5,
    )

    assert result is fake_product
    repo.create.assert_awaited_once_with(
        tenant_id=42,
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
            tenant_id=1,
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

    await svc.list_active_products(repo, tenant_id=7, page=2, page_size=10)

    repo.list_active.assert_awaited_once_with(tenant_id=7, limit=10, offset=20)


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
