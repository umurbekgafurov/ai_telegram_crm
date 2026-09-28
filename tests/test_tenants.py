"""Unit tests for app.services.tenants."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant
from app.services import tenants as svc


@pytest.mark.asyncio
async def test_get_or_create_default_tenant_creates() -> None:
    session = MagicMock(spec=AsyncSession)
    fake = Tenant(name="Default Shop", slug="default", is_active=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.database.repositories.tenants.TenantRepository.get_or_create_default",
            AsyncMock(return_value=fake),
        )
        result = await svc.get_or_create_default_tenant(
            session, name="Default Shop", slug="default"
        )

    assert result is fake
    assert result.slug == "default"


@pytest.mark.asyncio
async def test_get_or_create_default_tenant_idempotent() -> None:
    session = MagicMock(spec=AsyncSession)
    existing = Tenant(id=1, name="Default Shop", slug="default", is_active=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.database.repositories.tenants.TenantRepository.get_or_create_default",
            AsyncMock(return_value=existing),
        )
        first = await svc.get_or_create_default_tenant(
            session, name="Default Shop", slug="default"
        )
        second = await svc.get_or_create_default_tenant(
            session, name="Default Shop", slug="default"
        )

    assert first.id == second.id == 1


@pytest.mark.asyncio
async def test_get_tenant_by_slug() -> None:
    session = MagicMock(spec=AsyncSession)
    fake = Tenant(id=5, name="X", slug="x-shop", is_active=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.database.repositories.tenants.TenantRepository.get_by_slug",
            AsyncMock(return_value=fake),
        )
        result = await svc.get_tenant_by_slug(session, slug="x-shop")

    assert result is fake
    assert result.slug == "x-shop"
