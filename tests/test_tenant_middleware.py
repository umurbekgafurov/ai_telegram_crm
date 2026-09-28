"""Test TenantMiddleware with real aiogram Update.

This test verifies that TenantMiddleware reads `data["event_from_user"]`
(aiogram 3 injects it) rather than `event.from_user` (which doesn't exist
on Update).

Requires Postgres (models use JSONB).

Run: pytest tests/test_tenant_middleware.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, Update, User as TgUser

from app.middlewares.tenant import TenantMiddleware


def _make_real_update(telegram_id: int) -> Update:
    """Build a real aiogram Update object (not a MagicMock)."""
    tg_user = TgUser(id=telegram_id, is_bot=False, first_name="Test")
    chat = Chat(id=telegram_id, type="private")
    msg = Message(
        message_id=1,
        date=0,
        chat=chat,
        from_user=tg_user,
        text="/start",
    )
    return Update(update_id=1, message=msg)


class _CaptureHandler:
    """Fake downstream handler that captures injected data."""

    def __init__(self) -> None:
        self.captured: dict = {}

    async def __call__(self, event, data):
        self.captured["tenant_id"] = data.get("tenant_id")
        self.captured["membership_role"] = data.get("membership_role")
        self.captured["db_user"] = data.get("db_user")
        return "handled"


@pytest.mark.asyncio
async def test_middleware_reads_event_from_user() -> None:
    """TenantMiddleware must inject tenant_id + membership_role.

    With the buggy implementation (`event.from_user`), this test FAILS
    because `Update` has no `.from_user`.
    """
    mw = TenantMiddleware()
    handler = _CaptureHandler()

    # --- mock session with two sequential queries -----------------------
    fake_user = MagicMock()
    fake_user.id = 42

    fake_membership = MagicMock()
    fake_membership.tenant_id = 7
    fake_membership.role = "ADMIN"

    call_count = {"n": 0}

    async def fake_execute(stmt):
        result = MagicMock()
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First query: User lookup
            result.scalar_one_or_none = MagicMock(return_value=fake_user)
        else:
            # Second query: Membership join
            result.scalar_one_or_none = MagicMock(return_value=fake_membership)
        return result

    session = MagicMock()
    session.execute = fake_execute

    update = _make_real_update(telegram_id=615532128)

    # aiogram 3 normally injects event_from_user into `data`.
    # Simulate the real dispatcher here:
    data: dict = {
        "session": session,
        "event_from_user": update.message.from_user,
    }

    await mw(handler, update, data)

    assert handler.captured["tenant_id"] == 7, (
        "TenantMiddleware failed to inject tenant_id. "
        "Did it read event.from_user instead of data['event_from_user']?"
    )
    assert handler.captured["membership_role"] == "ADMIN"
    assert handler.captured["db_user"] is fake_user