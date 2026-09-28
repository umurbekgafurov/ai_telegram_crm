"""M2.2 D: mark users.role as LEGACY (comment only, no data change).

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "d4e5f6a1b2c3"
down_revision: str | None = "c3d4e5f6a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # We do NOT drop users.role in M2.2 (backward compat).
    # We document its new status via a Postgres column comment.
    op.execute(
        "COMMENT ON COLUMN users.role IS "
        "'LEGACY: kept for backward compatibility during M2.2. "
        "Authorization MUST use tenant_memberships.role.'"
    )


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN users.role IS NULL")
