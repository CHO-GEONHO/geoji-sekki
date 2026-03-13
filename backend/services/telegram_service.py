"""Telegram 알림 서비스."""

import logging
import httpx

from backend.config import settings

logger = logging.getLogger("geojisekki.telegram")


async def send_message(text: str):
    """Telegram 메시지 전송"""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram 설정 없음 — 스킵")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            resp.raise_for_status()
    except Exception as e:
        logger.error("Telegram 전송 실패: %s", e)


async def notify_crawl_result(crawler_name: str, status: str, items: int, duration: float, error: str = None):
    """크롤러 결과 알림"""
    emoji = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"
    text = (
        f"{emoji} <b>[{crawler_name}]</b> 크롤링 {status}\n"
        f"수집: {items}개 | 소요: {duration:.1f}초"
    )
    if error:
        text += f"\n에러: <code>{error[:200]}</code>"

    await send_message(text)


async def notify_feed_generated(date_str: str, items_count: int, model: str):
    """피드 생성 완료 알림"""
    await send_message(
        f"🍚 <b>거지세끼 피드 생성 완료</b>\n"
        f"날짜: {date_str}\n"
        f"아이템: {items_count}개\n"
        f"모델: {model}"
    )


async def send_daily_report():
    """일일 크롤링 요약 리포트"""
    from sqlalchemy import select, func
    from datetime import datetime, timedelta
    from backend.database import async_session
    from backend.models import CrawlLog

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as session:
        result = await session.execute(
            select(
                CrawlLog.crawler_name,
                CrawlLog.status,
                func.sum(CrawlLog.items_count),
            )
            .where(CrawlLog.finished_at >= today)
            .group_by(CrawlLog.crawler_name, CrawlLog.status)
        )
        rows = result.all()

    if not rows:
        return

    lines = ["📊 <b>일일 크롤링 리포트</b>\n"]
    for name, status, count in rows:
        emoji = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"
        lines.append(f"  {emoji} {name}: {status} ({count}개)")

    await send_message("\n".join(lines))
