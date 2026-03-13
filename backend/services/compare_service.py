"""편의점 간 가격 비교 서비스."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CvsProduct
from backend.crawlers.pyony_crawler import _get_week_key


async def compare_product(
    session: AsyncSession,
    product_name: str,
    week_key: Optional[str] = None,
) -> Optional[dict]:
    """같은 상품명이 여러 편의점에서 행사 중일 때 비교.

    반환:
        {"product_name": ..., "stores": [...], "cheapest": "gs25"}
    """
    week_key = week_key or _get_week_key()

    result = await session.execute(
        select(CvsProduct)
        .where(
            CvsProduct.name.ilike(f"%{product_name}%"),
            CvsProduct.week_key == week_key,
        )
        .order_by(CvsProduct.unit_price.asc())
    )
    products = result.scalars().all()

    if not products:
        return None

    stores = []
    for p in products:
        stores.append({
            "store": p.store,
            "price": p.price,
            "event_type": p.event_type,
            "unit_price": p.unit_price,
        })

    return {
        "product_name": product_name,
        "stores": stores,
        "cheapest": stores[0]["store"] if stores else "",
    }
