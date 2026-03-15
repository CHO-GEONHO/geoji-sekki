"""AI 데일리 피드 생성 서비스.

매일 07:30 KST 실행:
1. 오늘 기준 활성 데이터 수집 (편의점/뽐뿌/올영/다이소)
2. DeepSeek에 전달 → 5~7개 피드 카드 선정
3. 거지세끼 톤 카피 생성
4. feeds 테이블 저장
5. 실패 시 전날 피드 재사용
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select, desc, func

from backend.database import async_session
from backend.models import CvsProduct, Hotdeal, OliveyoungDeal, DaisoProduct, Feed
from backend.services.llm_service import llm_service
from backend.crawlers.pyony_crawler import _get_week_key
from backend.crawlers.daiso_crawler import _get_month_key

logger = logging.getLogger("geojisekki.feed")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "daily_feed.txt"


async def generate_daily_feed(target_date: Optional[date] = None) -> dict:
    """데일리 피드 생성.

    반환: {"date": "2026-03-13", "items": [...], "model": "deepseek-chat"}
    """
    today = target_date or date.today()
    date_str = today.isoformat()

    # 이미 생성된 피드가 있으면 반환
    async with async_session() as session:
        existing = await session.execute(
            select(Feed).where(Feed.date == date_str)
        )
        feed = existing.scalar_one_or_none()
        if feed:
            logger.info("[feed] %s 피드 이미 존재 — 스킵", date_str)
            return {
                "date": date_str,
                "items": json.loads(feed.items),
                "model": feed.model,
            }

    try:
        # 1. 활성 데이터 수집
        collected = await _collect_active_data(today)

        if not collected:
            logger.warning("[feed] 수집된 데이터 없음 — 전날 피드 재사용")
            return await _fallback_yesterday(today)

        # 2. LLM 호출
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        user_prompt = (
            f"오늘 날짜: {date_str}\n\n"
            f"오늘 수집된 데이터:\n{json.dumps(collected, ensure_ascii=False, indent=2)}"
        )

        result = await llm_service.chat_feed(
            system_prompt, user_prompt, max_tokens=4000
        )

        items = result["data"]
        if isinstance(items, dict):
            items = items.get("items", items.get("feed", []))

        # 3. 저장
        async with async_session() as session:
            feed = Feed(
                date=date_str,
                items=json.dumps(items, ensure_ascii=False),
                model=result["model"],
                prompt_tokens=result["tokens"]["prompt"],
                completion_tokens=result["tokens"]["completion"],
            )
            session.add(feed)
            await session.commit()

        logger.info(
            "[feed] %s 피드 생성 완료: %d개 아이템, model=%s",
            date_str, len(items), result["model"],
        )

        return {"date": date_str, "items": items, "model": result["model"]}

    except Exception as e:
        logger.error("[feed] 피드 생성 실패: %s — 전날 피드 재사용", e)
        return await _fallback_yesterday(today)


async def _collect_active_data(today: date) -> dict:
    """오늘 기준 활성 데이터 수집 — 소스별 최대 5개, 할인율/인기 기준 정렬."""
    data = {}

    async with async_session() as session:
        # 편의점: 이번 주 행사 상품 중 이벤트 타입별로 TOP 5씩 (1+1 우선)
        week_key = _get_week_key(today)
        cvs_result = await session.execute(
            select(CvsProduct)
            .where(CvsProduct.week_key == week_key)
            .order_by(CvsProduct.unit_price.asc())
            .limit(15)
        )
        cvs_items = cvs_result.scalars().all()
        CVS_SEARCH_URL = {
            "gs25": "https://www.gs25.com/goods/search.do?keyword=",
            "cu": "https://cu.bgfretail.com/product/search.do?searchWord=",
            "seven": "https://www.7eleven.co.kr/product/search.do?keyword=",
            "emart24": "https://store.emart24.co.kr/goods/search?keyword=",
        }
        if cvs_items:
            data["cvs"] = [
                {
                    "store": p.store, "name": p.name, "price": p.price,
                    "event_type": p.event_type, "category": p.category,
                    "unit_price": p.unit_price,
                    "effective_discount": (
                        "50%" if p.event_type == "1+1" else
                        "33%" if p.event_type == "2+1" else
                        "직접할인"
                    ),
                    "image_url": p.image_url,
                    "url": CVS_SEARCH_URL.get(p.store, "") + p.name,
                }
                for p in cvs_items
            ]

        # 뽐뿌: 최근 48시간 추천수 상위 5 (더 넓게 수집)
        two_days_ago = datetime.combine(today - timedelta(days=2), datetime.min.time())
        hotdeal_result = await session.execute(
            select(Hotdeal)
            .where(Hotdeal.crawled_at >= two_days_ago)
            .order_by(desc(Hotdeal.vote_count))
            .limit(5)
        )
        hotdeal_items = hotdeal_result.scalars().all()
        if hotdeal_items:
            data["hotdeals"] = [
                {
                    "title": h.title, "price_value": h.price_value,
                    "vote_count": h.vote_count, "category": h.category,
                    "summary": h.summary, "url": h.url,
                    "image_url": h.image_url,
                }
                for h in hotdeal_items
            ]

        # 올영: 할인율 상위 5개 (discount_rate DESC)
        oy_result = await session.execute(
            select(OliveyoungDeal)
            .where(OliveyoungDeal.discount_rate.isnot(None))
            .order_by(desc(OliveyoungDeal.discount_rate))
            .limit(5)
        )
        oy_items = oy_result.scalars().all()
        if oy_items:
            data["oliveyoung"] = [
                {
                    "name": o.name, "brand": o.brand,
                    "original_price": o.original_price,
                    "sale_price": o.sale_price,
                    "discount_rate": o.discount_rate,
                    "event_type": o.event_type, "category": o.category,
                    "image_url": o.image_url,
                    "url": o.url,
                }
                for o in oy_items
            ]

        # 다이소: 이번 달 AI 점수 상위 5
        month_key = _get_month_key(today)
        daiso_result = await session.execute(
            select(DaisoProduct)
            .where(DaisoProduct.month_key == month_key)
            .where(DaisoProduct.ai_score.isnot(None))
            .order_by(desc(DaisoProduct.ai_score))
            .limit(5)
        )
        daiso_items = daiso_result.scalars().all()
        if daiso_items:
            data["daiso"] = [
                {
                    "name": d.name, "price": d.price,
                    "category": d.category, "ai_score": d.ai_score,
                    "ai_comment": d.ai_comment,
                    "image_url": d.image_url,
                    "url": f"https://www.daiso.co.kr/goods/search.do?searchText={d.name}",
                }
                for d in daiso_items
            ]

    return data


async def _fallback_yesterday(today: date) -> dict:
    """전날 피드 재사용 (AI 실패 시 fallback)"""
    yesterday = (today - timedelta(days=1)).isoformat()

    async with async_session() as session:
        result = await session.execute(
            select(Feed).where(Feed.date == yesterday)
        )
        feed = result.scalar_one_or_none()

        if feed:
            items = json.loads(feed.items)
            # 제목에 표시
            for item in items:
                if "(어제 피드)" not in item.get("title", ""):
                    item["title"] = f"(어제 피드) {item['title']}"
            return {
                "date": today.isoformat(),
                "items": items,
                "model": f"{feed.model} (fallback)",
            }

    return {"date": today.isoformat(), "items": [], "model": "none"}
