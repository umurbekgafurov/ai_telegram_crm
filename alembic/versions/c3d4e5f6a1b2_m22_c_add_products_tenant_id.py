"""M2.2 C: add products.tenant_id + backfill from default tenant.

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-09-28
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a1b2"
down_revision: str | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _default_slug() -> str:
    return os.getenv("DEFAULT_TENANT_SLUG", "default")


def upgrade() -> None:
    # 1. Add nullable column
    op.add_column(
        "products",
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
    )

    # 2. Backfill from default tenant
    op.execute(
        sa.text(
            """
            UPDATE products
            SET tenant_id = (SELECT id FROM tenants WHERE slug = :slug)
            WHERE tenant_id IS NULL
            """
        ).bindparams(slug=_default_slug())
    )

    # 3. Verify backfill (fail loudly if any row is still NULL)
    bind = op.get_bind()
    remaining = bind.execute(
        sa.text("SELECT COUNT(*) FROM products WHERE tenant_id IS NULL")
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"Backfill failed: {remaining} products still have tenant_id IS NULL"
        )

    # 4. Enforce NOT NULL
    op.alter_column("products", "tenant_id", nullable=False)

    # 5. FK + index
    op.create_foreign_key(
        "fk_products_tenant_id",
        "products",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_products_tenant_id", table_name="products")
    op.drop_constraint("fk_products_tenant_id", "products", type_="foreignkey")
    op.drop_column("products", "tenant_id")
