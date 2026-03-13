"""올리브영 API — /api/oliveyoung"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import limiter
from backend.models import OliveyoungDeal
from backend.schemas import OliveyoungDealOut, OliveyoungCalendarItem

router = APIRouter(tags=["올리브영"])


@router.get("/oliveyoung", response_model=dict)
@limiter.limit("60/minute")
async def get_oliveyoung_deals(
    request: Request,
    category: Optional[str] = None,
    event_type: Optional[str] = None,
    sort: str = Query("discount", enum=["discount", "price", "latest"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """올리브영 세일 상품 목록"""
    query = select(OliveyoungDeal)

    if category:
        query = query.where(OliveyoungDeal.category == category)
    if event_type:
        query = query.where(OliveyoungDeal.event_type == event_type)

    # 정렬
    if sort == "discount":
        query = query.order_by(desc(OliveyoungDeal.discount_rate))
    elif sort == "price":
        query = query.order_by(OliveyoungDeal.sale_price.asc())
    else:
        query = query.order_by(desc(OliveyoungDeal.crawled_at))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [OliveyoungDealOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/oliveyoung/categories", response_model=list[str])
@limiter.limit("30/minute")
async def get_oy_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OliveyoungDeal.category)
        .where(OliveyoungDeal.category.isnot(None))
        .distinct()
        .order_by(OliveyoungDeal.category)
    )
    return [row[0] for row in result.all()]


@router.get("/oliveyoung/calendar", response_model=list[OliveyoungCalendarItem])
@limiter.limit("30/minute")
async def get_oy_calendar(
    request: Request,
    year: int = Query(default=None),
):
    """올영세일/올영데이 일정 캘린더"""
    y = year or date.today().year
    events = []

    # 올영세일 (연 4회: 3, 6, 9, 12월)
    for month in [3, 6, 9, 12]:
        events.append(OliveyoungCalendarItem(
            event_name=f"{y}년 {month}월 올영세일",
            start_date=date(y, month, 1),
            end_date=date(y, month, 7),
            event_type="oliveyoung_sale",
        ))

    # 올영데이 (매월 25~27일)
    for month in range(1, 13):
        events.append(OliveyoungCalendarItem(
            event_name=f"{y}년 {month}월 올영데이",
            start_date=date(y, month, 25),
            end_date=date(y, month, 27),
            event_type="oliveyoung_day",
        ))

    return events
