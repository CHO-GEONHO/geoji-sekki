"""에펨코리아 핫딜 크롤러 (fmkorea.com).

fmkorea.com robots.txt 확인일: 2026-03-18
크롤링 범위: 핫딜 게시판 1~2페이지 (베스트 우선), 일 2회
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
from backend.database import async_session
from backend.models import Hotdeal
from backend.services.llm_service import llm_service

logger = logging.getLogger("geojisekki.crawler.fmkorea")

BASE_URL = "https://www.fmkorea.com"
HOTDEAL_URL = f"{BASE_URL}/hotdeal"

# 뽐뿌와 동일한 키워드 분류 테이블
CATEGORY_KEYWORDS = {
    "전자제품": ["노트북", "맥북", "아이패드", "갤럭시", "아이폰", "에어팟", "버즈", "모니터",
                "키보드", "마우스", "SSD", "그래픽카드", "태블릿", "워치", "이어폰", "헤드폰",
                "충전기", "보조배터리", "TV", "로봇청소기", "건조기", "세탁기", "냉장고"],
    "식품": ["치킨", "피자", "커피", "음료", "과자", "라면", "배달", "맥주", "소주",
            "고기", "쌀", "밀키트", "도시락", "빵", "아이스크림"],
    "패션": ["신발", "나이키", "아디다스", "뉴발란스", "자켓", "패딩", "운동화", "가방",
            "지갑", "벨트", "옷", "티셔츠", "청바지"],
    "뷰티": ["스킨", "로션", "세럼", "마스크팩", "선크림", "화장품", "향수", "샴푸",
            "올리브영"],
    "생활용품": ["세제", "휴지", "물티슈", "칫솔", "치약", "세탁", "주방", "욕실"],
    "여행": ["항공", "호텔", "숙박", "여행", "렌터카", "비행기", "리조트"],
    "도서/문화": ["책", "공연", "영화", "넷플릭스", "유튜브", "게임", "스팀", "콘솔",
                 "플스", "닌텐도", "스위치"],
}


def _classify_by_keyword(title: str) -> Optional[str]:
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return None


def _parse_price(text: str) -> Optional[int]:
    if not text:
        return None
    numbers = re.findall(r"\d+", text.replace(",", ""))
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            return None
    return None


class FmkoreaCrawler(BaseCrawler):
    name = "fmkorea"
    min_expected_items = 5
    max_pages = 2

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Referer": "https://www.fmkorea.com/",
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
            url = f"{HOTDEAL_URL}?page={page}"
            try:
                html = await self.fetch(url)
                page_items = self._parse_page(html)
                items.extend(page_items)
                logger.info("[fmkorea] page %d: %d개 수집", page, len(page_items))
                if page < self.max_pages:
                    await self.delay()
            except Exception as e:
                logger.error("[fmkorea] page %d 크롤링 실패: %s", page, e)

        # 추천수 0이면서 댓글도 없는 스팸성 제거
        items = [i for i in items if i["vote_count"] > 0 or i["comment_count"] > 2]

        items = await self._classify_items(items)
        return items

    def _parse_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 에펨코리아 XE 게시판: ul#board_list li.ub-content
        rows = soup.select("ul#board_list li.ub-content")
        if not rows:
            # fallback: div.fm_best_widget 베스트 위젯도 시도
            rows = soup.select("div.hotdeal_var8 ul li")

        for row in rows:
            try:
                item = self._parse_row(row)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug("[fmkorea] 행 파싱 실패: %s", e)

        return items

    def _parse_row(self, row: BeautifulSoup) -> Optional[dict]:
        # 제목 — h3.title a 또는 a.hx
        title_el = row.select_one("h3.title a") or row.select_one("a.hx")
        if not title_el:
            return None

        # 카테고리 프리픽스 "[전자제품]" 등 제거
        title = title_el.get_text(strip=True)
        title = re.sub(r"^\[[^\]]*\]\s*", "", title)
        if not title or len(title) < 3:
            return None

        # URL
        href = title_el.get("href", "")
        if not href:
            return None
        url = urljoin(BASE_URL, href) if not href.startswith("http") else href
        # 에펨코리아 게시글 URL 패턴: /board_id/post_no 형태
        if "fmkorea.com" not in url:
            return None

        # 추천수 — .recom_count span 또는 .recom_count
        vote_count = 0
        vote_el = row.select_one(".recom_count span") or row.select_one(".recom_count")
        if vote_el:
            vote_text = vote_el.get_text(strip=True)
            vote_match = re.search(r"\d+", vote_text)
            vote_count = int(vote_match.group()) if vote_match else 0

        # 댓글수 — .num_comment 또는 .comment_count
        comment_count = 0
        comment_el = row.select_one(".num_comment") or row.select_one(".comment_count")
        if comment_el:
            comment_text = comment_el.get_text(strip=True)
            comment_match = re.search(r"\d+", comment_text)
            comment_count = int(comment_match.group()) if comment_match else 0

        # 가격 — .hotdeal_side 또는 제목에서 추출
        price_value = None
        price_el = row.select_one(".hotdeal_side .cost") or row.select_one(".cost")
        if price_el:
            price_value = _parse_price(price_el.get_text(strip=True))
        if price_value is None:
            price_value = _parse_price(title)

        # 이미지 — a.btn_thumb img 또는 .hotdeal_thumb img
        image_url = ""
        img_el = (
            row.select_one("a.btn_thumb img")
            or row.select_one(".hotdeal_thumb img")
            or row.select_one(".thumb img")
        )
        if img_el:
            image_url = img_el.get("src", "") or img_el.get("data-src", "")
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(BASE_URL, image_url)

        # 날짜 — .time abbr[title] 또는 span.time
        posted_at = None
        time_el = row.select_one("span.time abbr") or row.select_one(".time")
        if time_el:
            date_text = time_el.get("title", "") or time_el.get_text(strip=True)
            for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%m.%d %H:%M"):
                try:
                    posted_at = datetime.strptime(date_text[:len(fmt)], fmt)
                    if posted_at.year == 1900:
                        posted_at = posted_at.replace(year=datetime.now().year)
                    break
                except ValueError:
                    continue

        category = _classify_by_keyword(title)

        return {
            "source": "fmkorea",
            "title": title,
            "price": str(price_value) if price_value else None,
            "price_value": price_value,
            "original_price": None,
            "discount_rate": None,
            "vote_count": vote_count,
            "comment_count": comment_count,
            "url": url,
            "category": category,
            "summary": None,
            "image_url": image_url or None,
            "posted_at": posted_at,
        }

    async def _classify_items(self, items: list[dict]) -> list[dict]:
        """키워드 미분류 아이템만 LLM 배치 분류"""
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
            classified = await llm_service.batch_classify(unclassified, system_prompt)
            class_map = {c["id"]: c for c in classified}
            for idx, item in enumerate(items):
                if idx in class_map:
                    item["category"] = class_map[idx].get("category", "기타")
                    item["summary"] = class_map[idx].get("summary")
        except Exception as e:
            logger.warning("[fmkorea] AI 분류 실패: %s", e)
            for item in items:
                if item["category"] is None:
                    item["category"] = "기타"

        return items

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

        crawl_started = datetime.utcnow()
        async with async_session() as session:
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

            # 이번 크롤에 없던 에펨 게시글 삭제
            result = await session.execute(
                delete(Hotdeal).where(
                    Hotdeal.source == "fmkorea",
                    Hotdeal.crawled_at < crawl_started,
                )
            )
            deleted = result.rowcount
            if deleted:
                logger.info("[fmkorea] stale 항목 %d개 삭제", deleted)

            await session.commit()
            return len(items)
