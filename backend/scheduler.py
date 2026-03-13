"""APScheduler 크롤링 스케줄 관리.

FastAPI lifespan에서 start_scheduler()로 시작.
모든 시간은 KST (Asia/Seoul).

스케줄:
  편의점:   매주 월 06:00
  뽐뿌:    매일 08:00, 18:00
  올영:    주 2회 (월/목) 07:00
  다이소:   월 2회 (1일, 15일) 07:00
  피드 생성: 매일 07:30
  일일 리포트: 매일 08:00
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("geojisekki.scheduler")

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


# ── 크롤러 실행 래퍼 ──
async def run_pyony():
    from backend.crawlers.pyony_crawler import PyonyCrawler
    from backend.services.telegram_service import notify_crawl_result
    crawler = PyonyCrawler()
    try:
        count = await crawler.run()
        await notify_crawl_result("pyony", "success", count, 0)
    except Exception as e:
        await notify_crawl_result("pyony", "failed", 0, 0, str(e))


async def run_ppomppu():
    from backend.crawlers.ppomppu_crawler import PpomppuCrawler
    from backend.services.telegram_service import notify_crawl_result
    crawler = PpomppuCrawler()
    try:
        count = await crawler.run()
        await notify_crawl_result("ppomppu", "success", count, 0)
    except Exception as e:
        await notify_crawl_result("ppomppu", "failed", 0, 0, str(e))


async def run_oliveyoung():
    from backend.crawlers.oliveyoung_crawler import OliveyoungCrawler
    from backend.services.telegram_service import notify_crawl_result
    crawler = OliveyoungCrawler()
    try:
        count = await crawler.run()
        await notify_crawl_result("oliveyoung", "success", count, 0)
    except Exception as e:
        await notify_crawl_result("oliveyoung", "failed", 0, 0, str(e))


async def run_daiso():
    from backend.crawlers.daiso_crawler import DaisoCrawler
    from backend.services.telegram_service import notify_crawl_result
    crawler = DaisoCrawler()
    try:
        count = await crawler.run()
        await notify_crawl_result("daiso", "success", count, 0)
    except Exception as e:
        await notify_crawl_result("daiso", "failed", 0, 0, str(e))


async def run_feed_generation():
    from backend.services.feed_service import generate_daily_feed
    from backend.services.telegram_service import notify_feed_generated
    try:
        result = await generate_daily_feed()
        await notify_feed_generated(result["date"], len(result["items"]), result["model"])
    except Exception as e:
        logger.error("피드 생성 스케줄 실패: %s", e)


async def run_daily_report():
    from backend.services.telegram_service import send_daily_report
    await send_daily_report()


def start_scheduler():
    """스케줄러 시작 — FastAPI lifespan에서 호출"""

    # 편의점: 매주 월 06:00 KST
    scheduler.add_job(
        run_pyony,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="pyony",
        replace_existing=True,
    )

    # 뽐뿌: 매일 08:00, 18:00 KST
    scheduler.add_job(
        run_ppomppu,
        CronTrigger(hour=8, minute=0),
        id="ppomppu_morning",
        replace_existing=True,
    )
    scheduler.add_job(
        run_ppomppu,
        CronTrigger(hour=18, minute=0),
        id="ppomppu_evening",
        replace_existing=True,
    )

    # 올영: 주 2회 (월/목) 07:00 KST
    scheduler.add_job(
        run_oliveyoung,
        CronTrigger(day_of_week="mon,thu", hour=7, minute=0),
        id="oliveyoung",
        replace_existing=True,
    )

    # 다이소: 월 2회 (1일, 15일) 07:00 KST
    scheduler.add_job(
        run_daiso,
        CronTrigger(day="1,15", hour=7, minute=0),
        id="daiso",
        replace_existing=True,
    )

    # 피드 생성: 매일 07:30 KST
    scheduler.add_job(
        run_feed_generation,
        CronTrigger(hour=7, minute=30),
        id="feed_generation",
        replace_existing=True,
    )

    # 일일 리포트: 매일 08:00 KST
    scheduler.add_job(
        run_daily_report,
        CronTrigger(hour=20, minute=0),  # 20:00 KST = 하루 마감
        id="daily_report",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler 시작 — %d개 작업 등록", len(scheduler.get_jobs()))
