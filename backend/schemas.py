from datetime import datetime, date
from pydantic import BaseModel


# ── 편의점 ──
class CvsProductOut(BaseModel):
    id: int
    store: str
    name: str
    price: int
    event_type: str
    category: str | None = None
    unit_price: int | None = None
    image_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    week_key: str

    model_config = {"from_attributes": True}


class CvsCompareItem(BaseModel):
    store: str
    price: int
    event_type: str
    unit_price: int | None = None


class CvsCompareOut(BaseModel):
    product_name: str
    stores: list[CvsCompareItem]
    cheapest: str  # 가장 싼 편의점


# ── 핫딜 ──
class HotdealOut(BaseModel):
    id: int
    source: str
    title: str
    price: str | None = None
    price_value: int | None = None
    discount_rate: int | None = None
    vote_count: int
    comment_count: int
    url: str
    category: str | None = None
    summary: str | None = None
    image_url: str | None = None
    posted_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── 올리브영 ──
class OliveyoungDealOut(BaseModel):
    id: int
    name: str
    brand: str | None = None
    original_price: int | None = None
    sale_price: int | None = None
    discount_rate: int | None = None
    event_type: str | None = None
    category: str | None = None
    url: str | None = None
    image_url: str | None = None
    is_oliveyoung_pick: bool
    start_date: date | None = None
    end_date: date | None = None

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
    category: str | None = None
    is_new: bool
    ranking: int | None = None
    url: str | None = None
    image_url: str | None = None
    ai_score: float | None = None
    ai_comment: str | None = None
    month_key: str

    model_config = {"from_attributes": True}


# ── 피드 ──
class FeedItem(BaseModel):
    title: str
    body: str
    source: str           # cvs, hotdeal, oliveyoung, daiso
    store: str | None = None
    category: str | None = None
    priority: int = 0
    url: str | None = None


class FeedOut(BaseModel):
    date: str
    items: list[FeedItem]
    created_at: datetime | None = None


# ── 헬스 체크 ──
class CrawlerHealth(BaseModel):
    last_success: datetime | None = None
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
