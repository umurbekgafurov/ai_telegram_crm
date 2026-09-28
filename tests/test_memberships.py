"""Unit tests for app.services.memberships."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMembership
from app.services import memberships as svc


@pytest.mark.asyncio
async def test_ensure_membership_creates() -> None:
    session = MagicMock(spec=AsyncSession)
    fake = TenantMembership(
        id=1, tenant_id=10, user_id=20, role="ADMIN", is_active=True
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.database.repositories.memberships.MembershipRepository.get_or_create",
            AsyncMock(return_value=(fake, True)),
        )
        result = await svc.ensure_membership(
            session, tenant_id=10, user_id=20, role="ADMIN"
        )

    assert result is fake
    assert result.role == "ADMIN"


@pytest.mark.asyncio
async def test_ensure_membership_idempotent() -> None:
    session = MagicMock(spec=AsyncSession)
    fake = TenantMembership(
        id=1, tenant_id=10, user_id=20, role="ADMIN", is_active=True
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.database.repositories.memberships.MembershipRepository.get_or_create",
            AsyncMock(return_value=(fake, False)),
        )
        result = await svc.ensure_membership(
            session, tenant_id=10, user_id=20, role="ADMIN"
        )

    assert result.id == 1


def test_role_is_admin_true_for_owner_and_admin() -> None:
    assert svc.role_is_admin("OWNER") is True
    assert svc.role_is_admin("ADMIN") is True


def test_role_is_admin_false_for_others() -> None:
    assert svc.role_is_admin("STAFF") is False
    assert svc.role_is_admin(None) is False
    assert svc.role_is_admin("") is False


def test_admin_roles_contains_owner_and_admin() -> None:
    assert "OWNER" in svc.ADMIN_ROLES
    assert "ADMIN" in svc.ADMIN_ROLES
