"""데일리 피드 API — /api/feed"""

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.deps import limiter
from backend.models import Feed
from backend.schemas import FeedOut, FeedItem

router = APIRouter(tags=["피드"])


@router.get("/feed", response_model=FeedOut | dict)
@limiter.limit("60/minute")
async def get_daily_feed(
    request: Request,
    target_date: Optional[str] = Query(None, alias="date", description="날짜 (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """오늘의 데일리 피드 (AI 큐레이션)

    Cache-Control: 5분
    """
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            return {"error": "날짜 형식: YYYY-MM-DD"}
        date_str = d.isoformat()
    else:
        date_str = date.today().isoformat()

    result = await db.execute(
        select(Feed).where(Feed.date == date_str)
    )
    feed = result.scalar_one_or_none()

    if not feed:
        return {"date": date_str, "items": [], "message": "아직 피드가 생성되지 않았어요"}

    items = json.loads(feed.items)

    return FeedOut(
        date=feed.date,
        items=[FeedItem(**item) for item in items],
        created_at=feed.created_at,
    )


@router.get("/feed/dates", response_model=list[str])
@limiter.limit("30/minute")
async def get_feed_dates(
    request: Request,
    limit: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """피드가 존재하는 날짜 목록 (최신순)"""
    result = await db.execute(
        select(Feed.date)
        .order_by(desc(Feed.date))
        .limit(limit)
    )
    return [row[0] for row in result.all()]


@router.post("/feed/generate", response_model=dict)
@limiter.limit("5/minute")
async def trigger_feed_generation(
    request: Request,
    target_date: Optional[str] = Query(None, alias="date"),
):
    """수동 피드 생성 트리거 (관리용)"""
    from backend.services.feed_service import generate_daily_feed

    d = None
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            return {"error": "날짜 형식: YYYY-MM-DD"}

    result = await generate_daily_feed(d)
    return {
        "status": "ok",
        "date": result["date"],
        "items_count": len(result["items"]),
        "model": result["model"],
    }
