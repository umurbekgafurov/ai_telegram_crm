"""M2.2.1-F: drop redundant indexes.

- ix_products_tenant_sku: redundant with uq_products_tenant_sku
- ix_tenants_slug:        redundant with uq_tenants_slug

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "f6a1b2c3d4e5"
down_revision: str | None = "e5f6a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_tenant_sku")
    op.execute("DROP INDEX IF EXISTS ix_tenants_slug")


def downgrade() -> None:
    op.create_index(
        "ix_products_tenant_sku", "products", ["tenant_id", "sku"], unique=False
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=False)
