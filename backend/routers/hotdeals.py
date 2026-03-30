"""핫딜 API — /api/hotdeals + /api/go (클릭 추적)"""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, async_session
from backend.deps import limiter
from backend.models import Hotdeal, ClickLog
from backend.schemas import HotdealOut

router = APIRouter(tags=["핫딜"])


class SortEnum(str, Enum):
    votes = "votes"
    latest = "latest"


@router.get("/hotdeals", response_model=dict)
@limiter.limit("60/minute")
async def get_hotdeals(
    request: Request,
    sort: SortEnum = SortEnum.votes,
    category: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """핫딜 목록 (추천순/최신순, 소스 필터 가능)"""
    query = select(Hotdeal)

    if source:
        query = query.where(Hotdeal.source == source)
    if category:
        query = query.where(Hotdeal.category == category)

    if sort == SortEnum.votes:
        query = query.order_by(desc(Hotdeal.vote_count))
    else:
        query = query.order_by(desc(Hotdeal.posted_at))

    # 총 건수
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 페이지네이션
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [HotdealOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit,
    }


@router.get("/hotdeals/categories", response_model=list[str])
@limiter.limit("30/minute")
async def get_hotdeal_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """핫딜 카테고리 목록"""
    result = await db.execute(
        select(Hotdeal.category)
        .where(Hotdeal.category.isnot(None))
        .distinct()
        .order_by(Hotdeal.category)
    )
    return [row[0] for row in result.all()]


@router.get("/go/{deal_id}")
async def redirect_deal(
    deal_id: int,
    request: Request,
):
    """원본 링크 리다이렉트 + 클릭 로그 기록 (수익화 기반)"""
    async with async_session() as session:
        # 딜 조회
        result = await session.execute(
            select(Hotdeal).where(Hotdeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()

        if not deal:
            return {"error": "딜을 찾을 수 없음"}

        # 클릭 로그 기록
        click = ClickLog(
            deal_id=deal_id,
            deal_type="hotdeal",
            user_agent=request.headers.get("user-agent", ""),
            referer=request.headers.get("referer", ""),
        )
        session.add(click)
        await session.commit()

        return RedirectResponse(url=deal.url, status_code=302)
