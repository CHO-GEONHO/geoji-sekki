"""다이소 API — /api/daiso"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import limiter
from backend.models import DaisoProduct
from backend.schemas import DaisoProductOut
from backend.crawlers.daiso_crawler import _get_month_key

router = APIRouter(tags=["다이소"])


@router.get("/daiso", response_model=dict)
@limiter.limit("60/minute")
async def get_daiso_products(
    request: Request,
    category: Optional[str] = None,
    price: Optional[int] = Query(None, description="가격대 필터 (1000,2000,3000,5000)"),
    month_key: Optional[str] = None,
    sort: str = Query("score", enum=["score", "ranking", "price"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """다이소 가성비템 목록"""
    mk = month_key or _get_month_key()
    query = select(DaisoProduct).where(DaisoProduct.month_key == mk)

    if category:
        query = query.where(DaisoProduct.category == category)
    if price:
        query = query.where(DaisoProduct.price == price)

    if sort == "score":
        query = query.order_by(desc(DaisoProduct.ai_score))
    elif sort == "ranking":
        query = query.order_by(DaisoProduct.ranking.asc())
    else:
        query = query.order_by(DaisoProduct.price.asc())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    from urllib.parse import quote

    def _daiso_out(d: DaisoProduct) -> DaisoProductOut:
        out = DaisoProductOut.model_validate(d)
        out.url = d.url or f"https://www.daiso.co.kr/search?search={quote(d.name)}"
        return out

    return {
        "items": [_daiso_out(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/daiso/new", response_model=dict)
@limiter.limit("60/minute")
async def get_daiso_new(
    request: Request,
    month_key: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """이번 달 다이소 신상품"""
    mk = month_key or _get_month_key()
    query = (
        select(DaisoProduct)
        .where(DaisoProduct.month_key == mk, DaisoProduct.is_new == True)
        .order_by(desc(DaisoProduct.ai_score))
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [DaisoProductOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/daiso/categories", response_model=list[str])
@limiter.limit("30/minute")
async def get_daiso_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DaisoProduct.category)
        .where(DaisoProduct.category.isnot(None))
        .distinct()
        .order_by(DaisoProduct.category)
    )
    return [row[0] for row in result.all()]
