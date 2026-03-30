"""관리자 API — /api/admin

크롤러 수동 실행, 상태 확인 등
"""

import logging
from fastapi import APIRouter, Request
from backend.deps import limiter

logger = logging.getLogger("geojisekki.admin")

router = APIRouter(prefix="/admin", tags=["관리"])


@router.post("/crawl/{crawler_name}")
@limiter.limit("5/minute")
async def trigger_crawl(crawler_name: str, request: Request):
    """크롤러 수동 실행 트리거

    사용 가능: pyony, ppomppu, ruliweb, oliveyoung, daiso, all
    """
    crawlers = {}

    if crawler_name in ("pyony", "all"):
        from backend.crawlers.pyony_crawler import PyonyCrawler
        crawlers["pyony"] = PyonyCrawler()

    if crawler_name in ("ppomppu", "all"):
        from backend.crawlers.ppomppu_crawler import PpomppuCrawler
        crawlers["ppomppu"] = PpomppuCrawler()

    if crawler_name in ("oliveyoung", "all"):
        from backend.crawlers.oliveyoung_crawler import OliveyoungCrawler
        crawlers["oliveyoung"] = OliveyoungCrawler()

    if crawler_name in ("daiso", "all"):
        from backend.crawlers.daiso_crawler import DaisoCrawler
        crawlers["daiso"] = DaisoCrawler()

    if crawler_name in ("ruliweb", "all"):
        from backend.crawlers.ruliweb_crawler import RuliwebCrawler
        crawlers["ruliweb"] = RuliwebCrawler()

    if not crawlers:
        return {"error": f"알 수 없는 크롤러: {crawler_name}",
                "available": ["pyony", "ppomppu", "ruliweb", "oliveyoung", "daiso", "all"]}

    results = {}
    for name, crawler in crawlers.items():
        try:
            count = await crawler.run()
            results[name] = {"status": "success", "items": count}
            logger.info("[admin] %s 수동 크롤링 완료: %d개", name, count)
        except Exception as e:
            results[name] = {"status": "failed", "error": str(e)}
            logger.error("[admin] %s 수동 크롤링 실패: %s", name, e)

    return {"results": results}


@router.post("/feed/generate")
@limiter.limit("5/minute")
async def trigger_feed(request: Request):
    """피드 수동 생성"""
    from backend.services.feed_service import generate_daily_feed

    try:
        result = await generate_daily_feed()
        return {
            "status": "ok",
            "date": result["date"],
            "items_count": len(result["items"]),
            "model": result["model"],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@router.get("/status")
@limiter.limit("30/minute")
async def get_status(request: Request):
    """전체 시스템 상태"""
    from sqlalchemy import select, func, desc
    from backend.database import async_session
    from backend.models import CvsProduct, Hotdeal, OliveyoungDeal, DaisoProduct, Feed, CrawlLog

    async with async_session() as session:
        counts = {}
        for name, model in [
            ("cvs_products", CvsProduct),
            ("hotdeals", Hotdeal),
            ("oliveyoung_deals", OliveyoungDeal),
            ("daiso_products", DaisoProduct),
            ("feeds", Feed),
        ]:
            result = await session.execute(select(func.count()).select_from(model))
            counts[name] = result.scalar() or 0

        # 최근 크롤 로그
        result = await session.execute(
            select(CrawlLog).order_by(desc(CrawlLog.finished_at)).limit(10)
        )
        logs = result.scalars().all()

    return {
        "table_counts": counts,
        "recent_crawl_logs": [
            {
                "crawler": log.crawler_name,
                "status": log.status,
                "items": log.items_count,
                "error": log.error_message,
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "duration": log.duration_seconds,
            }
            for log in logs
        ],
    }
