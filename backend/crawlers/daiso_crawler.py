"""다이소 가성비템 크롤러 (daisomall.co.kr).

크롤링 주기: 월 2회 (1일, 15일) 07:00
대상: 신상품 목록 + 베스트셀러 랭킹
AI: 가성비 점수 + 한줄 코멘트 배치 처리
"""

import logging
import re
from datetime import datetime, date
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import DaisoProduct
from backend.services.llm_service import llm_service

logger = logging.getLogger("geojisekki.crawler.daiso")

BASE_URL = "https://www.daiso.co.kr"

# 다이소 페이지 URL — JS 렌더링 필요 (Swiper 기반)
DAISO_URLS = {
    "new": f"{BASE_URL}/goods/new_arrival.do",
    "best": f"{BASE_URL}/goods/best_seller.do",
}

CATEGORY_KEYWORDS = {
    "생활용품": ["수납", "청소", "세탁", "정리", "걸이", "수건", "바구니", "박스"],
    "주방": ["주방", "접시", "컵", "그릇", "수저", "밀폐", "냄비", "프라이팬", "도마"],
    "문구": ["문구", "펜", "노트", "스티커", "테이프", "가위", "풀", "클립"],
    "뷰티": ["화장", "미용", "브러쉬", "퍼프", "거울", "화장솜", "면봉", "헤어"],
    "식품": ["과자", "음료", "커피", "차", "젤리", "사탕", "초콜릿"],
    "전자": ["충전", "케이블", "이어폰", "보조배터리", "USB", "LED", "건전지"],
    "인테리어": ["인테리어", "조명", "액자", "화분", "캔들", "디퓨저"],
    "패션잡화": ["양말", "장갑", "모자", "가방", "파우치", "지갑"],
}


def _get_month_key(d: date | None = None) -> str:
    d = d or date.today()
    return d.strftime("%Y-%m")


def _classify_daiso_category(name: str) -> str:
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "기타"


class DaisoCrawler(BaseCrawler):
    name = "daiso"
    min_expected_items = 10

    async def crawl(self) -> list[dict]:
        items = []

        for page_type, url in DAISO_URLS.items():
            # 다이소는 JS 렌더링 필수 → Playwright 우선
            try:
                page_items = await self._crawl_playwright(url, page_type)
                items.extend(page_items)
                logger.info("[daiso] %s: %d개 수집 (playwright)", page_type, len(page_items))
                await self.delay()
            except ImportError:
                logger.warning("[daiso] Playwright 미설치 — httpx fallback")
                try:
                    page_items = await self._crawl_page(url, page_type)
                    items.extend(page_items)
                except Exception as e2:
                    logger.error("[daiso] %s httpx도 실패: %s", page_type, e2)
            except Exception as e:
                logger.error("[daiso] %s Playwright 실패: %s", page_type, e)

        # AI 가성비 점수 (배치)
        items = await self._score_items(items)
        return items

    async def _crawl_page(self, url: str, page_type: str) -> list[dict]:
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "lxml")
        return self._parse_products(soup, page_type)

    async def _crawl_playwright(self, url: str, page_type: str) -> list[dict]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(800)

            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "lxml")
        return self._parse_products(soup, page_type)

    def _parse_products(self, soup: BeautifulSoup, page_type: str) -> list[dict]:
        products = []
        month_key = _get_month_key()

        cards = soup.select(
            ".product-item, .prd-item, [class*='product'], [class*='item-box']"
        )

        for idx, card in enumerate(cards):
            try:
                product = self._parse_single(card, page_type, month_key, idx + 1)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[daiso] 상품 파싱 실패: %s", e)

        return products

    def _parse_single(
        self, card: BeautifulSoup, page_type: str, month_key: str, rank: int
    ) -> dict | None:
        # 상품명
        name_el = card.select_one("[class*='name'], [class*='title'], h3, h4, a")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name or len(name) < 2:
            return None

        # 가격
        price_el = card.select_one("[class*='price'], .price, span")
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = int(re.sub(r"[^\d]", "", price_text) or "0")
        # 다이소 가격대: 1000, 2000, 3000, 5000
        if price <= 0 or price > 10000:
            price = 1000  # 기본값

        # 이미지
        img_el = card.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(BASE_URL, image_url)

        # URL
        link_el = card.select_one("a[href]")
        url = ""
        if link_el:
            href = link_el.get("href", "")
            url = urljoin(BASE_URL, href)

        category = _classify_daiso_category(name)

        return {
            "name": name,
            "price": price,
            "category": category,
            "is_new": page_type == "new",
            "ranking": rank if page_type == "best" else None,
            "url": url or None,
            "image_url": image_url or None,
            "ai_score": None,
            "ai_comment": None,
            "month_key": month_key,
        }

    async def _score_items(self, items: list[dict]) -> list[dict]:
        """AI 가성비 점수 배치 처리 (20개씩)"""
        if not items:
            return items

        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "prompts" / "daiso_score.txt"
            system_prompt = prompt_path.read_text(encoding="utf-8")

            # 배치 분할 (20개씩)
            batch_size = 20
            for i in range(0, len(items), batch_size):
                batch = [
                    {"id": j, "name": items[j]["name"], "price": items[j]["price"],
                     "category": items[j]["category"]}
                    for j in range(i, min(i + batch_size, len(items)))
                ]

                user_prompt = (
                    "아래 다이소 상품들의 가성비 점수와 한줄 코멘트를 작성해줘.\n"
                    "JSON 배열로만 응답. 각 아이템에 id, score, comment 포함.\n\n"
                    + str(batch)
                )

                result = await llm_service.chat_json(system_prompt, user_prompt)
                scored = result["data"]
                if isinstance(scored, dict):
                    scored = scored.get("items", [])

                score_map = {s["id"]: s for s in scored}
                for j in range(i, min(i + batch_size, len(items))):
                    if j in score_map:
                        items[j]["ai_score"] = score_map[j].get("score")
                        items[j]["ai_comment"] = score_map[j].get("comment")

        except Exception as e:
            logger.warning("[daiso] AI 점수 부여 실패: %s", e)

        return items

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

        async with async_session() as session:
            saved = 0
            for item in items:
                stmt = sqlite_insert(DaisoProduct).values(**item)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["name", "month_key"],
                    set_={
                        "price": stmt.excluded.price,
                        "category": stmt.excluded.category,
                        "is_new": stmt.excluded.is_new,
                        "ranking": stmt.excluded.ranking,
                        "image_url": stmt.excluded.image_url,
                        "ai_score": stmt.excluded.ai_score,
                        "ai_comment": stmt.excluded.ai_comment,
                        "crawled_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                saved += 1

            await session.commit()
            return saved
