"""M2.2 E: composite uniqueness on products (tenant_id, sku|name).

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a1b2c3d4"
down_revision: str | None = "d4e5f6a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _check_duplicates(table: str, column: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            f"""
            SELECT tenant_id, {column}, COUNT(*) AS c
            FROM {table}
            GROUP BY tenant_id, {column}
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if rows:
        sample = rows[:5]
        raise RuntimeError(
            f"Duplicate {column!r} within tenant detected in {table}: "
            f"{len(rows)} group(s). Samples: {sample}. "
            "Resolve manually before applying this migration."
        )


def upgrade() -> None:
    # Safety: verify no duplicates before adding unique constraints.
    _check_duplicates("products", "sku")
    _check_duplicates("products", "name")

    # Drop old global unique constraints (from earlier migrations).
    # Names may differ; drop defensively.
    op.execute(
        "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key"
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_products_sku"  # old unique index
    )

    # New composite constraints
    op.create_unique_constraint(
        "uq_products_tenant_sku", "products", ["tenant_id", "sku"]
    )
    op.create_unique_constraint(
        "uq_products_tenant_name", "products", ["tenant_id", "name"]
    )

    # Non-unique index on sku for lookups within tenant
    op.create_index(
        "ix_products_tenant_sku", "products", ["tenant_id", "sku"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_products_tenant_sku", table_name="products")
    op.drop_constraint("uq_products_tenant_name", "products", type_="unique")
    op.drop_constraint("uq_products_tenant_sku", "products", type_="unique")

    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
