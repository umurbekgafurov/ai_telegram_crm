"""M2.2 A: create tenants table + default tenant.

Revision ID: a1b2c3d4e5f6
Revises: b7c8d9e0f1a2
Create Date: 2026-09-28
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _default_name() -> str:
    return os.getenv("DEFAULT_TENANT_NAME", "Default Shop")


def _default_slug() -> str:
    return os.getenv("DEFAULT_TENANT_SLUG", "default")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=False)

    # Default tenant (idempotent)
    op.execute(
        sa.text(
            """
            INSERT INTO tenants (name, slug, is_active)
            VALUES (:name, :slug, true)
            ON CONFLICT (slug) DO NOTHING
            """
        ).bindparams(name=_default_name(), slug=_default_slug())
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
