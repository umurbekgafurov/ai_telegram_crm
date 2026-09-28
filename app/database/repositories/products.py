"""Async repository for Product persistence operations (tenant-aware).

Every business query MUST be scoped by tenant_id. Cross-tenant reads are
never allowed from business code paths.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Product


class ProductRepository:
    """Encapsulates all database access for the Product entity.

    All business methods require tenant_id.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: int,
        name: str,
        sku: str,
        price: Decimal,
        cost_price: Decimal = Decimal("0"),
        stock_quantity: int = 0,
        category_id: int | None = None,
        description: str | None = None,
        photos: list[str] | None = None,
    ) -> Product:
        """Create and persist a new product owned by `tenant_id`."""
        product = Product(
            tenant_id=tenant_id,
            name=name,
            sku=sku,
            price=price,
            cost_price=cost_price,
            stock_quantity=stock_quantity,
            category_id=category_id,
            description=description,
            photos=photos or [],
        )
        self._session.add(product)
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def get_by_id(self, tenant_id: int, product_id: int) -> Product | None:
        """Fetch a product by id, scoped to tenant."""
        result = await self._session.execute(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, tenant_id: int, sku: str) -> Product | None:
        """Fetch a product by SKU within a tenant."""
        result = await self._session.execute(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.sku == sku,
            )
        )
        return result.scalar_one_or_none()

    async def list_active(
        self,
        *,
        tenant_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """List active (non-archived) products for a tenant, newest first."""
        result = await self._session.execute(
            select(Product)
            .where(
                Product.tenant_id == tenant_id,
                Product.status == "active",
            )
            .order_by(Product.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update(
        self, tenant_id: int, product_id: int, **fields: Any
    ) -> Product:
        """Partially update a product's fields (tenant-scoped).

        Raises:
            ValueError: if the product does not exist within this tenant,
                        or an unknown field is passed.
        """
        product = await self.get_by_id(tenant_id, product_id)
        if product is None:
            raise ValueError(
                f"Product with id={product_id} not found in tenant={tenant_id}"
            )

        allowed_fields = {
            "name",
            "sku",
            "price",
            "cost_price",
            "stock_quantity",
            "category_id",
            "description",
            "photos",
            "status",
        }
        for key, value in fields.items():
            if key not in allowed_fields:
                raise ValueError(f"Cannot update unknown field {key!r} on Product")
            setattr(product, key, value)

        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def soft_delete(self, tenant_id: int, product_id: int) -> bool:
        """Mark a product as archived (tenant-scoped).

        Returns:
            True if a product was found and archived, False otherwise.
        """
        product = await self.get_by_id(tenant_id, product_id)
        if product is None:
            return False
        product.status = "archived"
        await self._session.flush()
        return True
