"""Unit tests for app.services.users (M2.2 tenant-aware)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant, User
from app.services import users as svc


def _mock_session_returning(user: User | None) -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def _patch_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_or_create(session, *, name, slug):
        return Tenant(id=1, name=name, slug=slug, is_active=True)

    async def fake_ensure(session, *, tenant_id, user_id, role):
        return MagicMock()

    monkeypatch.setattr(
        "app.services.users.get_or_create_default_tenant",
        fake_get_or_create,
    )
    monkeypatch.setattr(
        "app.services.users.ensure_membership",
        fake_ensure,
    )


@pytest.mark.asyncio
async def test_upsert_user_creates_new(_patch_tenant) -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=123,
        username="alice",
        first_name="Alice",
        admin_ids=[],
        default_tenant_name="Default Shop",
        default_tenant_slug="default",
    )

    assert user.telegram_id == 123
    assert user.role == "customer"
    session.add.assert_called_once()
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_user_updates_existing(_patch_tenant) -> None:
    existing = User(
        telegram_id=123, username="old", first_name="Old", role="customer"
    )
    session = _mock_session_returning(existing)

    user = await svc.upsert_user(
        session,
        telegram_id=123,
        username="new",
        first_name="New",
        admin_ids=[],
        default_tenant_name="Default Shop",
        default_tenant_slug="default",
    )

    assert user.username == "new"
    assert user.first_name == "New"
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_user_promotes_admin(_patch_tenant) -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=999,
        username="boss",
        first_name="Boss",
        admin_ids=[999],
        default_tenant_name="Default Shop",
        default_tenant_slug="default",
    )

    assert user.role == "admin"


@pytest.mark.asyncio
async def test_upsert_user_non_admin_stays_customer(_patch_tenant) -> None:
    session = _mock_session_returning(None)

    user = await svc.upsert_user(
        session,
        telegram_id=555,
        username="u",
        first_name="U",
        admin_ids=[999],
        default_tenant_name="Default Shop",
        default_tenant_slug="default",
    )

    assert user.role == "customer"
