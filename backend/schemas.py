from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel


# ── 편의점 ──
class CvsProductOut(BaseModel):
    id: int
    store: str
    name: str
    price: int
    event_type: str
    category: Optional[str] = None
    unit_price: Optional[int] = None
    image_url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    week_key: str

    model_config = {"from_attributes": True}


class CvsCompareItem(BaseModel):
    store: str
    price: int
    event_type: str
    unit_price: Optional[int] = None


class CvsCompareOut(BaseModel):
    product_name: str
    stores: list[CvsCompareItem]
    cheapest: str  # 가장 싼 편의점


# ── 핫딜 ──
class HotdealOut(BaseModel):
    id: int
    source: str
    title: str
    price: Optional[str] = None
    price_value: Optional[int] = None
    discount_rate: Optional[int] = None
    vote_count: int
    comment_count: int
    url: str
    category: Optional[str] = None
    summary: Optional[str] = None
    image_url: Optional[str] = None
    posted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── 올리브영 ──
class OliveyoungDealOut(BaseModel):
    id: int
    name: str
    brand: Optional[str] = None
    original_price: Optional[int] = None
    sale_price: Optional[int] = None
    discount_rate: Optional[int] = None
    event_type: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    is_oliveyoung_pick: bool
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    model_config = {"from_attributes": True}


class OliveyoungCalendarItem(BaseModel):
    event_name: str
    start_date: date
    end_date: date
    event_type: str  # oliveyoung_sale, oliveyoung_day


# ── 다이소 ──
class DaisoProductOut(BaseModel):
    id: int
    name: str
    price: int
    category: Optional[str] = None
    is_new: bool
    ranking: Optional[int] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    ai_score: Optional[float] = None
    ai_comment: Optional[str] = None
    month_key: str

    model_config = {"from_attributes": True}


# ── 피드 ──
class FeedItem(BaseModel):
    title: str
    body: str
    source: str           # cvs, hotdeal, oliveyoung, daiso
    store: Optional[str] = None
    category: Optional[str] = None
    priority: int = 0
    url: Optional[str] = None
    image_url: Optional[str] = None
    keyword: Optional[str] = None


class FeedOut(BaseModel):
    date: str
    items: list[FeedItem]
    created_at: Optional[datetime] = None


# ── 헬스 체크 ──
class CrawlerHealth(BaseModel):
    last_success: Optional[datetime] = None
    items: int = 0
    status: str = "unknown"


class HealthOut(BaseModel):
    status: str
    crawlers: dict[str, CrawlerHealth]
    feed: dict
    db_size_mb: float


# ── 공통 ──
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
