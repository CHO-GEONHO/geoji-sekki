from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, Date,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# 1. 편의점 행사 상품
# ─────────────────────────────────────────────
class CvsProduct(Base):
    __tablename__ = "cvs_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store = Column(String(20), nullable=False)       # gs25, cu, seven, emart24
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)           # 정가 (원)
    event_type = Column(String(20), nullable=False)   # 1+1, 2+1, 3+1, discount
    category = Column(String(50))                     # 음료, 과자, 간편식사, ...
    unit_price = Column(Integer)                      # 개당 실질 가격
    image_url = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    week_key = Column(String(10), nullable=False)     # 2026-W11

    __table_args__ = (
        UniqueConstraint("store", "name", "week_key", name="uq_cvs_product"),
        Index("idx_cvs_week", "week_key"),
        Index("idx_cvs_store", "store"),
        Index("idx_cvs_category", "category"),
    )


# ─────────────────────────────────────────────
# 2. 핫딜 (뽐뿌 등)
# ─────────────────────────────────────────────
class Hotdeal(Base):
    __tablename__ = "hotdeals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(30), nullable=False)       # ppomppu, fmkorea, clien
    title = Column(String(500), nullable=False)
    price = Column(String(100))                       # 가격 텍스트
    price_value = Column(Integer)                     # 파싱된 가격
    original_price = Column(Integer)
    discount_rate = Column(Integer)                   # %
    vote_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    url = Column(Text, nullable=False)
    category = Column(String(50))                     # AI 분류
    summary = Column(Text)                            # AI 한줄 요약
    image_url = Column(Text)
    posted_at = Column(DateTime)
    crawled_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("url", name="uq_hotdeal_url"),
        Index("idx_hotdeals_date", "posted_at"),
        Index("idx_hotdeals_votes", "vote_count"),
    )


# ─────────────────────────────────────────────
# 3. 올리브영 세일
# ─────────────────────────────────────────────
class OliveyoungDeal(Base):
    __tablename__ = "oliveyoung_deals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    brand = Column(String(100))
    original_price = Column(Integer)
    sale_price = Column(Integer)
    discount_rate = Column(Integer)                   # %
    event_type = Column(String(30))                   # sale, 1+1, pick_special, limited
    category = Column(String(50))                     # 스킨케어, 메이크업, ...
    url = Column(Text)
    image_url = Column(Text)
    is_oliveyoung_pick = Column(Boolean, default=False)
    start_date = Column(Date)
    end_date = Column(Date)
    crawled_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "brand", "event_type",
                         name="uq_oy_product"),
        Index("idx_oy_date", "crawled_at"),
        Index("idx_oy_category", "category"),
        Index("idx_oy_discount", "discount_rate"),
    )


# ─────────────────────────────────────────────
# 4. 다이소 상품
# ─────────────────────────────────────────────
class DaisoProduct(Base):
    __tablename__ = "daiso_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    price = Column(Integer, nullable=False)           # 1000, 2000, 3000, 5000
    category = Column(String(50))
    is_new = Column(Boolean, default=False)
    ranking = Column(Integer)
    url = Column(Text)
    image_url = Column(Text)
    ai_score = Column(Float)                          # 가성비 점수 0~10
    ai_comment = Column(Text)                         # AI 한줄 코멘트
    month_key = Column(String(10), nullable=False)    # 2026-03
    crawled_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "month_key", name="uq_daiso_product"),
        Index("idx_daiso_month", "month_key"),
        Index("idx_daiso_ranking", "ranking"),
    )


# ─────────────────────────────────────────────
# 5. AI 피드
# ─────────────────────────────────────────────
class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, unique=True)  # 2026-03-13
    items = Column(Text, nullable=False)               # JSON 배열
    model = Column(String(50))                         # 사용된 LLM 모델
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# 6. 크롤링 로그
# ─────────────────────────────────────────────
class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    crawler_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)        # success, failed, partial
    items_count = Column(Integer, default=0)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    started_at = Column(DateTime)
    finished_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# 7. 클릭 추적 (수익화 기반)
# ─────────────────────────────────────────────
class ClickLog(Base):
    __tablename__ = "click_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Integer, nullable=False)
    deal_type = Column(String(30), nullable=False)     # cvs, hotdeal, oliveyoung, daiso
    user_agent = Column(Text)
    referer = Column(Text)
    clicked_at = Column(DateTime, default=datetime.utcnow)
