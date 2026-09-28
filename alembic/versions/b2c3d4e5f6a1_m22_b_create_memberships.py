"""M2.2 B: create tenant_memberships + backfill admin/manager users.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-28
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _default_slug() -> str:
    return os.getenv("DEFAULT_TENANT_SLUG", "default")


def upgrade() -> None:
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"
        ),
    )
    op.create_index(
        "ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"]
    )
    op.create_index(
        "ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"]
    )

    # Backfill: admin/manager users -> ADMIN membership in default tenant
    default_slug = _default_slug()
    op.execute(
        sa.text(
            """
            INSERT INTO tenant_memberships (tenant_id, user_id, role, is_active)
            SELECT
                (SELECT id FROM tenants WHERE slug = :slug),
                u.id,
                'ADMIN',
                true
            FROM users u
            WHERE u.role IN ('admin', 'manager')
              AND NOT EXISTS (
                  SELECT 1 FROM tenant_memberships tm
                  WHERE tm.user_id = u.id
                    AND tm.tenant_id = (SELECT id FROM tenants WHERE slug = :slug)
              )
            """
        ).bindparams(slug=default_slug)
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_memberships_user_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
