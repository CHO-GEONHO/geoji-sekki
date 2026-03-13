"""편의점 행사 API — /api/cvs"""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import limiter
from backend.models import CvsProduct
from backend.schemas import CvsProductOut, CvsCompareOut
from backend.services.compare_service import compare_product
from backend.crawlers.pyony_crawler import _get_week_key

router = APIRouter(tags=["편의점"])


class StoreEnum(str, Enum):
    gs25 = "gs25"
    cu = "cu"
    seven = "seven"
    emart24 = "emart24"


class EventTypeEnum(str, Enum):
    one_plus_one = "1+1"
    two_plus_one = "2+1"
    three_plus_one = "3+1"
    discount = "discount"
    bonus = "bonus"


@router.get("/cvs", response_model=dict)
@limiter.limit("60/minute")
async def get_cvs_products(
    request: Request,
    store: Optional[StoreEnum] = None,
    category: Optional[str] = None,
    event_type: Optional[EventTypeEnum] = None,
    week_key: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """편의점 행사 상품 목록 (필터 + 페이지네이션)"""
    wk = week_key or _get_week_key()
    query = select(CvsProduct).where(CvsProduct.week_key == wk)

    if store:
        query = query.where(CvsProduct.store == store.value)
    if category:
        query = query.where(CvsProduct.category == category)
    if event_type:
        query = query.where(CvsProduct.event_type == event_type.value)

    # 총 건수
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # 페이지네이션
    query = query.order_by(CvsProduct.unit_price.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [CvsProductOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/cvs/compare")
@limiter.limit("60/minute")
async def compare_cvs_product(
    request: Request,
    product: str = Query(..., min_length=1, description="검색할 상품명"),
    week_key: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """편의점 간 가격 비교"""
    result = await compare_product(db, product, week_key)
    if not result:
        return {"message": f"'{product}' 검색 결과 없음", "stores": []}
    return result


@router.get("/cvs/categories", response_model=list[str])
@limiter.limit("30/minute")
async def get_cvs_categories(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """사용 가능한 카테고리 목록"""
    result = await db.execute(
        select(CvsProduct.category)
        .where(CvsProduct.category.isnot(None))
        .distinct()
        .order_by(CvsProduct.category)
    )
    return [row[0] for row in result.all()]
