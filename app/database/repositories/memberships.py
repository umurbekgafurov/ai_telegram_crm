"""Async repository for TenantMembership persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant, TenantMembership


class MembershipRepository:
    """Encapsulates DB access for TenantMembership."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: str,
        is_active: bool = True,
    ) -> TenantMembership:
        membership = TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            is_active=is_active,
        )
        self._session.add(membership)
        await self._session.flush()
        return membership

    async def get_by_tenant_and_user(
        self, *, tenant_id: int, user_id: int
    ) -> TenantMembership | None:
        result = await self._session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(
        self, *, user_id: int
    ) -> list[TenantMembership]:
        result = await self._session.execute(
            select(TenantMembership)
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.is_active.is_(True),
            )
            .order_by(TenantMembership.id)
        )
        return list(result.scalars().all())

    async def get_first_active_with_tenant(
        self, *, user_id: int
    ) -> tuple[TenantMembership, Tenant] | None:
        """Resolve the user's primary (first) active tenant + membership.

        Used by the tenant middleware for single-tenant-compatible resolution.
        """
        result = await self._session.execute(
            select(TenantMembership, Tenant)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.is_active.is_(True),
                Tenant.is_active.is_(True),
            )
            .order_by(TenantMembership.id)
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def get_or_create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        role: str,
    ) -> tuple[TenantMembership, bool]:
        """Idempotent create-or-return. Returns (membership, created)."""
        existing = await self.get_by_tenant_and_user(
            tenant_id=tenant_id, user_id=user_id
        )
        if existing is not None:
            return existing, False
        m = await self.create(tenant_id=tenant_id, user_id=user_id, role=role)
        return m, True
