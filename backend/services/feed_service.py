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

from sqlalchemy import select, desc, func, exists

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

    # 이미 생성된 피드가 있으면 신규 항목만 추가 시도
    existing_items: list = []
    existing_titles: set[str] = set()
    async with async_session() as session:
        existing = await session.execute(
            select(Feed).where(Feed.date == date_str)
        )
        feed = existing.scalar_one_or_none()
        if feed:
            existing_items = json.loads(feed.items)
            # 만료된 항목 먼저 제거
            existing_items = await _filter_stale_items(existing_items, today)
            existing_titles = {item.get("title", "") for item in existing_items}
            logger.info("[feed] %s 피드 이미 존재 (%d개) — 신규 항목 확인", date_str, len(existing_items))

    try:
        # 1. 활성 데이터 수집
        collected = await _collect_active_data(today)

        if not collected:
            logger.warning("[feed] 수집된 데이터 없음 — 전날 피드 재사용")
            return await _fallback_yesterday(today)

        # 2. LLM 호출
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        already_covered = (
            f"\n\n이미 오늘 피드에 있는 항목 제목 (중복 금지):\n"
            + "\n".join(f"- {t}" for t in existing_titles)
            if existing_titles else ""
        )
        user_prompt = (
            f"오늘 날짜: {date_str}\n\n"
            f"오늘 수집된 데이터:\n{json.dumps(collected, ensure_ascii=False, indent=2)}"
            f"{already_covered}"
        )

        result = await llm_service.chat_feed(
            system_prompt, user_prompt, max_tokens=4000
        )

        new_items = result["data"]
        if isinstance(new_items, dict):
            new_items = new_items.get("items", new_items.get("feed", []))

        # 기존 항목과 중복 제목 필터링
        new_items = [i for i in new_items if i.get("title", "") not in existing_titles]

        # 3. 저장 (기존 피드가 있으면 append, 없으면 신규 생성)
        async with async_session() as session:
            existing_row = await session.execute(
                select(Feed).where(Feed.date == date_str)
            )
            feed_row = existing_row.scalar_one_or_none()

            if feed_row and new_items:
                # 기존 피드에 신규 항목 추가 (existing_items는 이미 stale 제거된 상태)
                all_items = existing_items + new_items
                feed_row.items = json.dumps(all_items, ensure_ascii=False)
                feed_row.model = result["model"]
                items = all_items
                logger.info("[feed] %s 피드 업데이트: +%d개 추가 (총 %d개)", date_str, len(new_items), len(all_items))
            elif feed_row:
                # 신규 항목 없음 — stale 제거 결과만 반영
                feed_row.items = json.dumps(existing_items, ensure_ascii=False)
                logger.info("[feed] %s 피드 신규 항목 없음 — 유지 (%d개)", date_str, len(existing_items))
                items = existing_items
            else:
                # 오늘 첫 피드 생성
                items = new_items
                feed_row = Feed(
                    date=date_str,
                    items=json.dumps(items, ensure_ascii=False),
                    model=result["model"],
                    prompt_tokens=result["tokens"]["prompt"],
                    completion_tokens=result["tokens"]["completion"],
                )
                session.add(feed_row)
                logger.info("[feed] %s 피드 신규 생성: %d개", date_str, len(items))

            await session.commit()

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
        CVS_BRAND_URL = {
            "gs25":    "https://pyony.com/brands/gs25/",
            "cu":      "https://pyony.com/brands/cu/",
            "seven":   "https://pyony.com/brands/seveneleven/",
            "emart24": "https://pyony.com/brands/emart24/",
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
                    "url": CVS_BRAND_URL.get(p.store, "https://pyony.com"),
                }
                for p in cvs_items
            ]

        # 핫딜 (뽐뿌 + 에펨코리아): 최근 48시간, 소스별 추천수 상위 8개씩
        two_days_ago = datetime.combine(today - timedelta(days=2), datetime.min.time())
        hotdeal_items = []
        for source in ("ppomppu", "fmkorea"):
            result = await session.execute(
                select(Hotdeal)
                .where(Hotdeal.source == source)
                .where(Hotdeal.crawled_at >= two_days_ago)
                .order_by(desc(Hotdeal.vote_count))
                .limit(8)
            )
            hotdeal_items.extend(result.scalars().all())

        if hotdeal_items:
            data["hotdeals"] = [
                {
                    "title": h.title, "price_value": h.price_value,
                    "vote_count": h.vote_count, "category": h.category,
                    "source_site": h.source,
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
                    "url": f"https://www.daiso.co.kr/search?search={d.name}",
                }
                for d in daiso_items
            ]

    return data


async def _filter_stale_items(items: list[dict], today: date) -> list[dict]:
    """피드 항목 중 DB에서 삭제된 항목 제거."""
    week_key = _get_week_key(today)
    month_key = _get_month_key(today)
    valid = []

    async with async_session() as session:
        for item in items:
            source = item.get("source", "")
            url = item.get("url", "")

            if source == "hotdeal" and url:
                row = await session.execute(
                    select(Hotdeal.id).where(Hotdeal.url == url).limit(1)
                )
                if row.scalar_one_or_none() is None:
                    logger.info("[feed] 만료 핫딜 제거: %s", item.get("title", ""))
                    continue

            elif source == "oliveyoung" and url:
                row = await session.execute(
                    select(OliveyoungDeal.id).where(OliveyoungDeal.url == url).limit(1)
                )
                if row.scalar_one_or_none() is None:
                    logger.info("[feed] 만료 올영 상품 제거: %s", item.get("title", ""))
                    continue

            elif source == "cvs":
                store = item.get("store", "")
                row = await session.execute(
                    select(CvsProduct.id)
                    .where(CvsProduct.week_key == week_key)
                    .where(CvsProduct.store == store if store else True)
                    .limit(1)
                )
                if row.scalar_one_or_none() is None:
                    logger.info("[feed] 만료 편의점 항목 제거: %s", item.get("title", ""))
                    continue

            elif source == "daiso":
                row = await session.execute(
                    select(DaisoProduct.id).where(DaisoProduct.month_key == month_key).limit(1)
                )
                if row.scalar_one_or_none() is None:
                    logger.info("[feed] 만료 다이소 항목 제거: %s", item.get("title", ""))
                    continue

            valid.append(item)

    removed = len(items) - len(valid)
    if removed:
        logger.info("[feed] stale 피드 항목 %d개 제거", removed)
    return valid


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
