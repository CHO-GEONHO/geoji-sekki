"""쿠팡 골드박스 API — /api/coupang"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import limiter
from backend.models import CoupangDeal
from backend.schemas import CoupangDealOut

router = APIRouter(tags=["쿠팡"])


@router.get("/coupang", response_model=dict)
@limiter.limit("60/minute")
async def get_coupang_deals(
    request: Request,
    category: Optional[str] = None,
    sort: str = Query("discount", enum=["discount", "price", "latest"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """쿠팡 골드박스 상품 목록"""
    query = select(CoupangDeal)

    if category:
        query = query.where(CoupangDeal.category == category)

    if sort == "discount":
        query = query.order_by(desc(CoupangDeal.discount_rate))
    elif sort == "price":
        query = query.order_by(CoupangDeal.sale_price.asc())
    else:
        query = query.order_by(desc(CoupangDeal.crawled_at))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [CoupangDealOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/coupang/categories", response_model=list[str])
@limiter.limit("30/minute")
async def get_coupang_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """쿠팡 카테고리 목록"""
    result = await db.execute(
        select(CoupangDeal.category)
        .where(CoupangDeal.category.isnot(None))
        .distinct()
        .order_by(CoupangDeal.category)
    )
    return [row[0] for row in result.all()]
