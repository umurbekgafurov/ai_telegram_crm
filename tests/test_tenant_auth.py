"""Unit tests for tenant-aware authorization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import admin_only, is_admin


def _mock_execute_scalar(value):
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_is_admin_true_for_owner() -> None:
    session = _mock_execute_scalar("OWNER")
    assert await is_admin(session, telegram_id=1) is True


@pytest.mark.asyncio
async def test_is_admin_true_for_admin() -> None:
    session = _mock_execute_scalar("ADMIN")
    assert await is_admin(session, telegram_id=1) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_staff() -> None:
    session = _mock_execute_scalar("STAFF")
    assert await is_admin(session, telegram_id=1) is False


@pytest.mark.asyncio
async def test_is_admin_false_when_no_membership() -> None:
    session = _mock_execute_scalar(None)
    assert await is_admin(session, telegram_id=1) is False


@pytest.mark.asyncio
async def test_admin_only_allows_admin_via_kwarg() -> None:
    @admin_only
    async def handler(event, session):
        return "ok"

    user = MagicMock(id=123)
    event = MagicMock(spec=Message)
    event.from_user = user

    result = await handler(
        event, session=MagicMock(), membership_role="ADMIN"
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin_via_kwarg() -> None:
    @admin_only
    async def handler(event, session):
        raise AssertionError("must not run")

    user = MagicMock(id=999)
    event = MagicMock(spec=CallbackQuery)
    event.from_user = user
    event.answer = AsyncMock()

    result = await handler(event, session=MagicMock(), membership_role=None)
    assert result is None
    event.answer.assert_awaited()


@pytest.mark.asyncio
async def test_admin_only_fails_closed_without_session() -> None:
    @admin_only
    async def handler(event, session):
        raise AssertionError("must not run")

    event = MagicMock(spec=Message)
    event.from_user = MagicMock(id=1)
    event.answer = AsyncMock()

    result = await handler(event)
    assert result is None
    event.answer.assert_awaited()
