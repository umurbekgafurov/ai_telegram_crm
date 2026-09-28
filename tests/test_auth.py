"""Unit tests for app.services.auth (tenant-aware)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import admin_only, is_admin


def _mock_execute_scalar(value):
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    session.execute = AsyncMock(return_value=result)
    return session


# --- is_admin --------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_true_for_owner_role() -> None:
    session = _mock_execute_scalar("OWNER")
    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_true_for_admin_role() -> None:
    session = _mock_execute_scalar("ADMIN")
    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_customer() -> None:
    session = _mock_execute_scalar("customer")
    assert await is_admin(session, 1) is False


@pytest.mark.asyncio
async def test_is_admin_false_for_unknown_user() -> None:
    session = _mock_execute_scalar(None)
    assert await is_admin(session, 1) is False


@pytest.mark.asyncio
async def test_is_admin_scoped_to_tenant() -> None:
    """When tenant_id is given, the query should include tenant_id."""
    session = _mock_execute_scalar("ADMIN")
    await is_admin(session, 1, tenant_id=42)

    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "tenant_id" in compiled


# --- admin_only decorator --------------------------------------------------


@pytest.mark.asyncio
async def test_admin_only_allows_admin_via_kwarg() -> None:
    @admin_only
    async def handler(event, session):
        return "ok"

    event = MagicMock()
    event.from_user = MagicMock(id=123)

    result = await handler(
        event, session=MagicMock(), membership_role="ADMIN"
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_admin_only_allows_owner_via_kwarg() -> None:
    @admin_only
    async def handler(event, session):
        return "ok"

    event = MagicMock()
    event.from_user = MagicMock(id=123)

    result = await handler(
        event, session=MagicMock(), membership_role="OWNER"
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin_via_kwarg() -> None:
    from aiogram.types import CallbackQuery

    @admin_only
    async def handler(event, session):
        raise AssertionError("must not run")

    event = MagicMock(spec=CallbackQuery)
    event.from_user = MagicMock(id=999)
    event.answer = AsyncMock()

    result = await handler(event, session=MagicMock(), membership_role="STAFF")
    assert result is None
    event.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_only_falls_back_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_is_admin(session, telegram_id, tenant_id=None):  # noqa: ANN001
        return True

    monkeypatch.setattr("app.services.auth.is_admin", fake_is_admin)

    @admin_only
    async def handler(event, session):
        return "ok"

    event = MagicMock()
    event.from_user = MagicMock(id=123)

    result = await handler(event, session=MagicMock())
    assert result == "ok"


@pytest.mark.asyncio
async def test_admin_only_fails_closed_without_session() -> None:
    from aiogram.types import Message

    @admin_only
    async def handler(event, session):
        raise AssertionError("must not run")

    event = MagicMock(spec=Message)
    event.from_user = MagicMock(id=1)
    event.answer = AsyncMock()

    result = await handler(event)
    assert result is None
    event.answer.assert_awaited()
