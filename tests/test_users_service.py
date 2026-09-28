"""Unit tests for app.services.users."""

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
