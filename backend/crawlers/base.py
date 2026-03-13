from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import httpx

from backend.database import async_session
from backend.models import CrawlLog

logger = logging.getLogger("geojisekki.crawler")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


class BaseCrawler(ABC):
    """크롤러 공통 베이스 클래스.

    하위 클래스에서 구현할 것:
        - name: 크롤러 이름 (e.g. "pyony")
        - min_expected_items: 최소 예상 아이템 수
        - crawl(): 데이터 수집 → parse → save 전체 파이프라인
    """

    name: str = "base"
    min_expected_items: int = 5
    max_retries: int = 3
    min_delay: float = 2.0
    max_delay: float = 5.0

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch(self, url: str, retries: Optional[int] = None) -> str:
        """URL 요청 + 재시도 (exponential backoff)"""
        retries = retries or self.max_retries
        client = await self.get_client()

        for attempt in range(retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "[%s] fetch 실패 (attempt %d/%d): %s — %s초 후 재시도",
                    self.name, attempt + 1, retries, e, f"{wait:.1f}",
                )
                if attempt < retries - 1:
                    await asyncio.sleep(wait)
                else:
                    raise

    async def delay(self):
        """요청 간 랜덤 딜레이"""
        wait = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(wait)

    @abstractmethod
    async def crawl(self) -> list[dict]:
        """크롤링 실행 → dict 리스트 반환"""
        ...

    @abstractmethod
    async def save(self, items: list[dict]) -> int:
        """DB 저장 → 저장된 건수 반환"""
        ...

    async def run(self) -> int:
        """전체 파이프라인: crawl → validate → save → log"""
        started_at = datetime.utcnow()
        start_time = time.monotonic()

        try:
            items = await self.crawl()

            if len(items) < self.min_expected_items:
                logger.warning(
                    "[%s] 수집 건수 부족: %d개 (최소 %d개 기대)",
                    self.name, len(items), self.min_expected_items,
                )

            saved_count = await self.save(items)
            duration = time.monotonic() - start_time

            logger.info(
                "[%s] 완료: 수집 %d개, 저장 %d개, %.1f초",
                self.name, len(items), saved_count, duration,
            )

            await self._log(
                status="success" if len(items) >= self.min_expected_items else "partial",
                items_count=saved_count,
                duration=duration,
                started_at=started_at,
            )
            return saved_count

        except Exception as e:
            duration = time.monotonic() - start_time
            logger.error("[%s] 크롤링 실패: %s", self.name, e, exc_info=True)
            await self._log(
                status="failed",
                items_count=0,
                duration=duration,
                started_at=started_at,
                error=str(e),
            )
            raise
        finally:
            await self.close()

    async def _log(
        self,
        status: str,
        items_count: int,
        duration: float,
        started_at: datetime,
        error: Optional[str] = None,
    ):
        """크롤링 결과를 crawl_logs에 기록"""
        async with async_session() as session:
            log = CrawlLog(
                crawler_name=self.name,
                status=status,
                items_count=items_count,
                error_message=error,
                duration_seconds=round(duration, 2),
                started_at=started_at,
            )
            session.add(log)
            await session.commit()

    async def is_healthy(self) -> dict:
        """최근 크롤링 상태 조회"""
        from sqlalchemy import select, desc
        async with async_session() as session:
            result = await session.execute(
                select(CrawlLog)
                .where(CrawlLog.crawler_name == self.name, CrawlLog.status == "success")
                .order_by(desc(CrawlLog.finished_at))
                .limit(1)
            )
            log = result.scalar_one_or_none()
            return {
                "last_success": log.finished_at.isoformat() if log else None,
                "items": log.items_count if log else 0,
                "status": "ok" if log else "never_run",
            }
