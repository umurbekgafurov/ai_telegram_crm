"""M2.0: TIMESTAMP -> TIMESTAMPTZ on timestamp columns + index on products.category_id.

Revision ID: b7c8d9e0f1a2
Revises: 852baa98043b
Create Date: 2026-09-27
"""

from __future__ import annotations
from collections.abc import Sequence
from alembic import op



revision: str = 'b7c8d9e0f1a2'
down_revision: str | None = '852baa98043b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing naive values were written by func.now() under Supabase's
    # default UTC server timezone. AT TIME ZONE 'UTC' reinterprets them
    # explicitly as UTC before attaching the zone, so no instant shifts.
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE categories "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN created_at TYPE TIMESTAMPTZ "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN updated_at TYPE TIMESTAMPTZ "
        "USING updated_at AT TIME ZONE 'UTC'"
    )
    op.create_index(
        op.f('ix_products_category_id'), 'products', ['category_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN updated_at TYPE TIMESTAMP "
        "USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE products "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE categories "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMP "
        "USING created_at AT TIME ZONE 'UTC'"
    )
