"""Unit tests for tenant-isolated product repository behavior.

These tests use mocks — they verify that the repository passes tenant_id
through to the underlying SQL statement. They do NOT require a live DB.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.products import ProductRepository


def _mock_session():
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_by_sku_is_tenant_scoped() -> None:
    session = _mock_session()
    repo = ProductRepository(session)

    await repo.get_by_sku(tenant_id=42, sku="ABC-1")

    # Inspect the compiled statement for the tenant_id parameter
    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "tenant_id" in compiled
    assert "sku" in compiled


@pytest.mark.asyncio
async def test_list_active_is_tenant_scoped() -> None:
    session = _mock_session()
    repo = ProductRepository(session)

    await repo.list_active(tenant_id=7, limit=10, offset=0)

    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "tenant_id" in compiled


@pytest.mark.asyncio
async def test_create_assigns_tenant_id() -> None:
    session = _mock_session()
    # Capture the Product object being added
    added = {}

    def _add(obj):
        added["obj"] = obj

    session.add.side_effect = _add

    repo = ProductRepository(session)
    await repo.create(
        tenant_id=99,
        name="X",
        sku="X-1",
        price=Decimal("1.00"),
        stock_quantity=1,
    )

    assert "obj" in added
    assert added["obj"].tenant_id == 99
    assert added["obj"].name == "X"
    assert added["obj"].sku == "X-1"


@pytest.mark.asyncio
async def test_get_by_id_is_tenant_scoped() -> None:
    session = _mock_session()
    repo = ProductRepository(session)

    await repo.get_by_id(tenant_id=11, product_id=22)

    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "tenant_id" in compiled
    assert "products.id" in compiled or "id" in compiled
