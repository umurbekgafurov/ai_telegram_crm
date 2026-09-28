"""Async repository for Tenant persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant


class TenantRepository:
    """Encapsulates DB access for Tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        is_active: bool = True,
    ) -> Tenant:
        tenant = Tenant(name=name, slug=slug, is_active=is_active)
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def get_by_id(self, tenant_id: int) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Tenant]:
        result = await self._session.execute(
            select(Tenant).where(Tenant.is_active.is_(True)).order_by(Tenant.id)
        )
        return list(result.scalars().all())

    async def get_or_create_default(
        self,
        *,
        name: str,
        slug: str,
    ) -> Tenant:
        """Idempotent: return existing tenant by slug, or create one."""
        existing = await self.get_by_slug(slug)
        if existing is not None:
            return existing
        return await self.create(name=name, slug=slug, is_active=True)
