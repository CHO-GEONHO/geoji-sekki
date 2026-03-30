"""루리웹 예판/핫딜 크롤러 (bbs.ruliweb.com).

bbs.ruliweb.com robots.txt 확인일: 2026-03-28
크롤링 범위: 예판 정보 게시판 1~2페이지, 일 2회
요청 간 2~5초 랜덤 딜레이 적용
"""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import delete

from backend.crawlers.base import BaseCrawler, USER_AGENTS
from backend.crawlers.ppomppu_crawler import CATEGORY_KEYWORDS, _classify_by_keyword, _parse_price
from backend.database import async_session
from backend.models import Hotdeal
from backend.services.llm_service import llm_service

logger = logging.getLogger("geojisekki.crawler.ruliweb")

BASE_URL = "https://bbs.ruliweb.com"
BOARD_URL = f"{BASE_URL}/news/board/1020"


class RuliwebCrawler(BaseCrawler):
    name = "ruliweb"
    min_expected_items = 3
    max_pages = 2

    async def get_client(self) -> httpx.AsyncClient:
        """루리웹 전용 클라이언트"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Referer": "https://bbs.ruliweb.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def crawl(self) -> list[dict]:
        items = []
        for page in range(1, self.max_pages + 1):
            url = f"{BOARD_URL}?page={page}"
            try:
                html = await self.fetch(url)
                page_items = self._parse_page(html)
                items.extend(page_items)
                logger.info("[ruliweb] page %d: %d개 수집", page, len(page_items))
                if page < self.max_pages:
                    await self.delay()
            except Exception as e:
                logger.error("[ruliweb] page %d 크롤링 실패: %s", page, e)

        # AI 분류 (키워드 매칭 실패한 아이템만)
        items = await self._classify_items(items)
        return items

    def _parse_page(self, html: str) -> list[dict]:
        """예판 정보 게시판 페이지 파싱"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        rows = soup.select("tr.table_body.blocktarget")

        for row in rows:
            try:
                item = self._parse_row(row)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug("[ruliweb] 행 파싱 실패: %s", e)

        return items

    def _parse_row(self, row: BeautifulSoup) -> Optional[dict]:
        """게시글 행 파싱"""
        # 제목 — td.subject > a.subject_link 내부 strong 또는 텍스트
        subject_td = row.select_one("td.subject")
        if not subject_td:
            return None

        link_el = subject_td.select_one("a.subject_link")
        if not link_el:
            return None

        # strong 태그 안에 실제 제목이 있음
        strong_el = link_el.select_one("strong")
        title = strong_el.get_text(strip=True) if strong_el else link_el.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # URL
        href = link_el.get("href", "")
        url = urljoin(BASE_URL, href) if href else ""
        if not url:
            return None

        # 추천수 — .recomd
        vote_count = 0
        recomd_el = row.select_one(".recomd")
        if recomd_el:
            vote_text = recomd_el.get_text(strip=True)
            vote_match = re.search(r"\d+", vote_text)
            vote_count = int(vote_match.group()) if vote_match else 0

        # 댓글수 — .num_reply
        comment_count = 0
        reply_el = row.select_one(".num_reply")
        if reply_el:
            reply_text = reply_el.get_text(strip=True)
            reply_match = re.search(r"\d+", reply_text)
            comment_count = int(reply_match.group()) if reply_match else 0

        # 가격 (제목에서 추출 시도)
        price_value = _parse_price(title)

        # 작성 시간 — td.time
        posted_at = None
        time_el = row.select_one("td.time")
        if time_el:
            date_text = time_el.get_text(strip=True)
            try:
                if ":" in date_text and len(date_text) <= 5:
                    # "HH:MM" — 오늘
                    parts = date_text.split(":")
                    posted_at = datetime.now().replace(
                        hour=int(parts[0]),
                        minute=int(parts[1]),
                        second=0, microsecond=0,
                    )
                elif "." in date_text:
                    # "YY.MM.DD" 또는 "YYYY.MM.DD"
                    posted_at = datetime.strptime(
                        date_text[:8] if len(date_text) <= 8 else date_text[:10],
                        "%y.%m.%d" if len(date_text) <= 8 else "%Y.%m.%d",
                    )
            except (ValueError, IndexError):
                pass

        # 키워드 기반 카테고리 분류
        category = _classify_by_keyword(title)

        return {
            "source": "ruliweb",
            "title": title,
            "price": title if price_value else None,
            "price_value": price_value,
            "original_price": None,
            "discount_rate": None,
            "vote_count": vote_count,
            "comment_count": comment_count,
            "url": url,
            "category": category,
            "summary": None,
            "image_url": None,
            "posted_at": posted_at,
        }

    async def _classify_items(self, items: list[dict]) -> list[dict]:
        """키워드 매칭 실패한 아이템만 LLM 배치 분류"""
        unclassified = [
            {"id": i, "title": item["title"]}
            for i, item in enumerate(items)
            if item["category"] is None
        ]

        if not unclassified:
            return items

        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "prompts" / "classify_hotdeals.txt"
            system_prompt = prompt_path.read_text(encoding="utf-8")

            classified = await llm_service.batch_classify(
                unclassified, system_prompt
            )

            class_map = {c["id"]: c for c in classified}
            for idx, item in enumerate(items):
                if idx in class_map:
                    item["category"] = class_map[idx].get("category", "기타")
                    item["summary"] = class_map[idx].get("summary")

        except Exception as e:
            logger.warning("[ruliweb] AI 분류 실패, 기타로 처리: %s", e)
            for item in items:
                if item["category"] is None:
                    item["category"] = "기타"

        return items

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

        crawl_started = datetime.utcnow()
        async with async_session() as session:
            saved = 0
            for item in items:
                stmt = sqlite_insert(Hotdeal).values(**item)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["url"],
                    set_={
                        "vote_count": stmt.excluded.vote_count,
                        "comment_count": stmt.excluded.comment_count,
                        "category": stmt.excluded.category,
                        "summary": stmt.excluded.summary,
                        "crawled_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                saved += 1

            # 이번 크롤에 없던 루리웹 게시글 삭제 (만료/삭제된 핫딜)
            result = await session.execute(
                delete(Hotdeal).where(
                    Hotdeal.source == "ruliweb",
                    Hotdeal.crawled_at < crawl_started,
                )
            )
            deleted = result.rowcount
            if deleted:
                logger.info("[ruliweb] stale 항목 %d개 삭제", deleted)

            await session.commit()
            return saved
