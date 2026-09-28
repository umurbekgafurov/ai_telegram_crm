"""Tenant membership business logic + role constants."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TenantMembership
from app.database.repositories.memberships import MembershipRepository

logger = logging.getLogger(__name__)

# M2.2 roles (tenant-scoped)
ROLE_OWNER = "OWNER"
ROLE_ADMIN = "ADMIN"

ADMIN_ROLES: frozenset[str] = frozenset({ROLE_OWNER, ROLE_ADMIN})


async def ensure_membership(
    session: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    role: str,
) -> TenantMembership:
    """Idempotently ensure a membership exists for (tenant, user)."""
    repo = MembershipRepository(session)
    membership, created = await repo.get_or_create(
        tenant_id=tenant_id, user_id=user_id, role=role
    )
    if created:
        logger.info(
            "Membership created: tenant_id=%s user_id=%s role=%s",
            tenant_id, user_id, role,
        )
    return membership


def role_is_admin(role: str | None) -> bool:
    """Return True if the membership role grants admin access."""
    return role in ADMIN_ROLES
