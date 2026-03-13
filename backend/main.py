import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.database import init_db, async_session
from backend.deps import limiter
from backend.models import CrawlLog, Feed

# ── 로깅 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            settings.log_path, maxBytes=10_000_000, backupCount=5,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("geojisekki")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.log_path).parent.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("거지세끼 서버 시작 🍚 port=%s", settings.app_port)

    # APScheduler (Phase 7에서 상세 등록)
    try:
        from backend.scheduler import start_scheduler
        start_scheduler()
        logger.info("스케줄러 시작")
    except ImportError:
        logger.info("스케줄러 모듈 없음 — 스킵")

    yield

    # Shutdown
    logger.info("거지세끼 서버 종료")


# ── App ──
app = FastAPI(
    title="거지세끼 API",
    description="매일 들어오는 절약 정보 큐레이션",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
from backend.routers import feed, cvs, oliveyoung, daiso, hotdeals
app.include_router(feed.router, prefix="/api")
app.include_router(cvs.router, prefix="/api")
app.include_router(oliveyoung.router, prefix="/api")
app.include_router(daiso.router, prefix="/api")
app.include_router(hotdeals.router, prefix="/api")

# ── Static Files (Frontend build) ──
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


# ── Health Check ──
@app.get("/api/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    import os
    from sqlalchemy import select, func, desc

    db_path = Path(settings.db_path)
    db_size_mb = round(db_path.stat().st_size / 1_048_576, 2) if db_path.exists() else 0

    crawlers = {}
    async with async_session() as session:
        for crawler_name in ["pyony", "ppomppu", "oliveyoung", "daiso"]:
            result = await session.execute(
                select(CrawlLog)
                .where(CrawlLog.crawler_name == crawler_name, CrawlLog.status == "success")
                .order_by(desc(CrawlLog.finished_at))
                .limit(1)
            )
            log = result.scalar_one_or_none()
            crawlers[crawler_name] = {
                "last_success": log.finished_at.isoformat() if log else None,
                "items": log.items_count if log else 0,
                "status": "ok" if log else "never_run",
            }

        # 최신 피드
        feed_result = await session.execute(
            select(Feed).order_by(desc(Feed.created_at)).limit(1)
        )
        latest_feed = feed_result.scalar_one_or_none()

    return {
        "status": "ok",
        "crawlers": crawlers,
        "feed": {
            "last_generated": latest_feed.created_at.isoformat() if latest_feed else None,
            "date": latest_feed.date if latest_feed else None,
        },
        "db_size_mb": db_size_mb,
    }
