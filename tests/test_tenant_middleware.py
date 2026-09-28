"""Test TenantMiddleware with a real aiogram Update.

CRITICAL:
- DB session is REAL (test Postgres), not mocked.
- Bot HTTP session is mocked so no Telegram API call is made.
- The middleware is exercised via Dispatcher.feed_update().
"""

from __future__ import annotations

import pytest
from aiogram import Bot, Dispatcher
from aiogram.dispatcher.middlewares.user_context import UserContextMiddleware
from aiogram.client.session.base import BaseSession
from aiogram.types import Chat, Message, Update, User as TgUser

from app.middlewares.db import DatabaseMiddleware
from app.middlewares.tenant import TenantMiddleware
from app.database.models import Tenant, TenantMembership, User


pytestmark = pytest.mark.asyncio


class _NoopSession(BaseSession):
    """Bot session that swallows all HTTP calls."""

    async def close(self) -> None:
        return None

    async def make_request(self, bot, method, timeout=None):  # type: ignore[override]
        # Return a benign default; tests don't rely on responses.
        from aiogram.methods import GetMe

        if isinstance(method, GetMe):
            return TgUser(id=1, is_bot=True, first_name="TestBot", username="test_bot")
        return True

    async def stream_content(self, *args, **kwargs):  # type: ignore[override]
        if False:
            yield b""
        return


def _make_update(telegram_id: int) -> Update:
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


async def _seed_admin(
    session_factory, telegram_id: int
) -> tuple[int, int]:
    """Insert tenant + user + ADMIN membership. Returns (tenant_id, user_id)."""
    async with session_factory() as s:
        tenant = Tenant(name="Test Shop", slug="test-shop-mw", is_active=True)
        s.add(tenant)
        await s.flush()

        user = User(
            telegram_id=telegram_id,
            username="t",
            first_name="Test",
            role="customer",
        )
        s.add(user)
        await s.flush()

        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="ADMIN",
            is_active=True,
        )
        s.add(membership)
        await s.commit()
        return tenant.id, user.id


async def _cleanup(session_factory, telegram_id: int) -> None:
    from sqlalchemy import delete

    async with session_factory() as s:
        # cascade removes membership
        await s.execute(delete(User).where(User.telegram_id == telegram_id))
        await s.execute(delete(Tenant).where(Tenant.slug == "test-shop-mw"))
        await s.commit()


async def test_middleware_reads_event_from_user(
    test_session_factory, monkeypatch
) -> None:
    """TenantMiddleware must inject tenant_id from a REAL Update.

    With the buggy implementation (event.from_user), the middleware never
    finds the user and tenant_id stays None -> test FAILS.
    """
    telegram_id = 999_000_001

    await _cleanup(test_session_factory, telegram_id)
    tenant_id, user_id = await _seed_admin(test_session_factory, telegram_id)

    # Patch the factory used by app.middlewares.db (imported by name!)
    monkeypatch.setattr(
        "app.middlewares.db.async_session_factory",
        test_session_factory,
    )

    captured: dict = {}

    dp = Dispatcher()
    # aiogram 3 installs UserContextMiddleware to inject event_from_user.
    # In production it is added by the real Dispatcher setup; here we add it
    # explicitly so the test mirrors production behaviour.
    dp.update.outer_middleware(UserContextMiddleware())
    dp.update.middleware(DatabaseMiddleware())   # injects session + repo
    dp.update.middleware(TenantMiddleware())     # uses session + event_from_user

    @dp.message()
    async def _capture(message, tenant_id=None, membership_role=None, db_user=None):
        captured["tenant_id"] = tenant_id
        captured["membership_role"] = membership_role
        captured["db_user"] = db_user
        return "ok"

    bot = Bot(token="123456:TEST", session=_NoopSession())
    update = _make_update(telegram_id)

    # aiogram 3 injects event_from_user; feed_update simulates the real path.
    await dp.feed_update(bot, update)

    await _cleanup(test_session_factory, telegram_id)

    assert captured.get("tenant_id") == tenant_id, (
        "TenantMiddleware failed to resolve tenant_id from real Update. "
        "Did it read event.from_user instead of data['event_from_user']?"
    )
    assert captured.get("membership_role") == "ADMIN"
    assert captured.get("db_user") is not None