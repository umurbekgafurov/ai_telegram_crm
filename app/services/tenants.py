"""Tenant business logic."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tenant
from app.database.repositories.tenants import TenantRepository

logger = logging.getLogger(__name__)


async def get_or_create_default_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
) -> Tenant:
    """Return the default tenant, creating it if necessary. Idempotent."""
    repo = TenantRepository(session)
    tenant = await repo.get_or_create_default(name=name, slug=slug)
    return tenant


async def get_tenant_by_slug(
    session: AsyncSession, *, slug: str
) -> Tenant | None:
    repo = TenantRepository(session)
    return await repo.get_by_slug(slug)
