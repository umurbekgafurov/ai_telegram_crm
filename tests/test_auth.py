"""Unit tests for app.services.auth (is_admin + @admin_only)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import admin_only, is_admin


# --- is_admin --------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_true_for_admin_role() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="admin")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_true_for_manager_role() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="manager")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_customer() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="customer")
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is False


@pytest.mark.asyncio
async def test_is_admin_false_for_unknown_user() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)

    assert await is_admin(session, 1) is False


# --- admin_only decorator --------------------------------------------------


@pytest.mark.asyncio
async def test_admin_only_allows_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_is_admin(session, telegram_id):  # noqa: ANN001
        return True

    monkeypatch.setattr("app.services.auth.is_admin", fake_is_admin)

    called: dict[str, bool] = {"hit": False}

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        called["hit"] = True
        return "ok"

    user = MagicMock()
    user.id = 123
    event = MagicMock()
    event.from_user = user

    result = await handler(event, session=MagicMock())
    assert result == "ok"
    assert called["hit"] is True


@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_is_admin(session, telegram_id):  # noqa: ANN001
        return False

    monkeypatch.setattr("app.services.auth.is_admin", fake_is_admin)

    from aiogram.types import CallbackQuery

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        raise AssertionError("handler must not run for non-admin")

    user = MagicMock()
    user.id = 999
    event = MagicMock(spec=CallbackQuery)
    event.from_user = user
    event.answer = AsyncMock()

    result = await handler(event, session=MagicMock())
    assert result is None
    event.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_only_fails_closed_without_session() -> None:
    from aiogram.types import Message

    @admin_only
    async def handler(event, session):  # noqa: ANN001
        raise AssertionError("handler must not run without session")

    event = MagicMock(spec=Message)
    event.from_user = MagicMock(id=123)
    event.answer = AsyncMock()

    result = await handler(event)  # no session kwarg
    assert result is None
    event.answer.assert_awaited()
