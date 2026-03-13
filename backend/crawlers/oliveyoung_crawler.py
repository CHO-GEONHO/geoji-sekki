"""올리브영 세일/1+1 크롤러 (oliveyoung.co.kr).

올리브영은 CSR 기반이라 모바일 웹 또는 내부 API 사용.
m.oliveyoung.co.kr의 XHR 요청을 캡처하여 JSON API 직접 호출.
API 없으면 Playwright headless로 fallback.

크롤링 주기: 주 2회 (월/목) 07:00
올영세일(3/6/9/12월), 올영데이(매월 25~27일) → 매일로 증가
"""

import logging
import re
from datetime import datetime, date
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import OliveyoungDeal

logger = logging.getLogger("geojisekki.crawler.oliveyoung")

# 올리브영 세일 페이지 URL (모바일 웹)
SALE_URLS = {
    "sale": "https://www.oliveyoung.co.kr/store/main/getSaleList.do",
    "best": "https://www.oliveyoung.co.kr/store/main/getBestList.do",
}

# 올리브영 API (내부 XHR) — 실제 배포 시 네트워크 탭에서 확인 후 업데이트
OY_API_BASE = "https://www.oliveyoung.co.kr/store/api"

CATEGORY_MAP = {
    "스킨케어": ["스킨", "토너", "에센스", "세럼", "크림", "로션", "앰플", "마스크팩"],
    "메이크업": ["파운데이션", "립", "아이", "블러셔", "쿠션", "틴트", "마스카라"],
    "헤어": ["샴푸", "트리트먼트", "헤어", "린스", "에센스"],
    "바디": ["바디", "핸드크림", "바디워시", "로션"],
    "건강": ["비타민", "유산균", "오메가", "콜라겐", "프로바이오틱스", "영양제"],
    "향수": ["향수", "퍼퓸", "오드"],
    "남성": ["남성", "맨즈", "쉐이빙"],
}


def _classify_oy_category(name: str, brand: str = "") -> str:
    text = f"{name} {brand}".lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in text:
                return category
    return "기타"


class OliveyoungCrawler(BaseCrawler):
    name = "oliveyoung"
    min_expected_items = 20
    _use_playwright = False

    async def crawl(self) -> list[dict]:
        """세일 상품 크롤링. httpx 우선, 실패 시 Playwright 전환."""
        items = []

        # 1차: httpx로 시도 (SSR 페이지 또는 API)
        try:
            items = await self._crawl_httpx()
            if items:
                return items
        except Exception as e:
            logger.warning("[oliveyoung] httpx 크롤링 실패: %s — Playwright 전환", e)

        # 2차: Playwright headless
        try:
            items = await self._crawl_playwright()
        except Exception as e:
            logger.error("[oliveyoung] Playwright 크롤링도 실패: %s", e)
            raise

        return items

    async def _crawl_httpx(self) -> list[dict]:
        """httpx로 올리브영 세일 페이지 크롤링"""
        items = []
        for sale_type, url in SALE_URLS.items():
            try:
                html = await self.fetch(url)
                soup = BeautifulSoup(html, "lxml")
                products = self._parse_products(soup, sale_type)
                items.extend(products)
                logger.info("[oliveyoung] %s: %d개 수집 (httpx)", sale_type, len(products))
                await self.delay()
            except Exception as e:
                logger.warning("[oliveyoung] %s httpx 실패: %s", sale_type, e)
        return items

    async def _crawl_playwright(self) -> list[dict]:
        """Playwright headless로 크롤링 (JS 렌더링 필요 시)"""
        from playwright.async_api import async_playwright

        items = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for sale_type, url in SALE_URLS.items():
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    # 스크롤 다운으로 lazy load 트리거
                    for _ in range(3):
                        await page.evaluate("window.scrollBy(0, 1000)")
                        await page.wait_for_timeout(1000)

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")
                    products = self._parse_products(soup, sale_type)
                    items.extend(products)
                    logger.info("[oliveyoung] %s: %d개 수집 (playwright)", sale_type, len(products))
                except Exception as e:
                    logger.error("[oliveyoung] %s playwright 실패: %s", sale_type, e)

            await browser.close()

        return items

    def _parse_products(self, soup: BeautifulSoup, sale_type: str) -> list[dict]:
        """올리브영 상품 목록 파싱"""
        products = []

        # 올리브영 상품 카드 셀렉터
        cards = soup.select(
            ".prd_info, .product-item, [class*='product'], [class*='prd']"
        )

        for card in cards:
            try:
                product = self._parse_single(card, sale_type)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[oliveyoung] 상품 파싱 실패: %s", e)

        return products

    def _parse_single(self, card: BeautifulSoup, sale_type: str) -> dict | None:
        """단일 상품 파싱"""
        # 상품명
        name_el = card.select_one(".prd_name, .product-name, a[class*='name']")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        # 브랜드
        brand_el = card.select_one(".prd_brand, .brand, [class*='brand']")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # 정가
        org_price_el = card.select_one(".org_price, .original-price, del, .price-original")
        org_price_text = org_price_el.get_text(strip=True) if org_price_el else ""
        original_price = int(re.sub(r"[^\d]", "", org_price_text) or "0") or None

        # 할인가
        sale_price_el = card.select_one(".sale_price, .final-price, .price-sale, .price")
        sale_price_text = sale_price_el.get_text(strip=True) if sale_price_el else ""
        sale_price = int(re.sub(r"[^\d]", "", sale_price_text) or "0") or None

        if not sale_price:
            return None

        # 할인율 계산
        discount_rate = None
        if original_price and sale_price and original_price > sale_price:
            discount_rate = round((1 - sale_price / original_price) * 100)

        # 이벤트 타입
        event_type = sale_type
        badge_el = card.select_one(".badge, .tag, [class*='event'], [class*='label']")
        if badge_el:
            badge_text = badge_el.get_text(strip=True).lower()
            if "1+1" in badge_text:
                event_type = "1+1"
            elif "픽" in badge_text or "pick" in badge_text:
                event_type = "pick_special"
            elif "한정" in badge_text or "limited" in badge_text:
                event_type = "limited"

        # 이미지
        img_el = card.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""
        if image_url and not image_url.startswith("http"):
            image_url = f"https://www.oliveyoung.co.kr{image_url}"

        # URL
        link_el = card.select_one("a[href]")
        url = ""
        if link_el:
            href = link_el.get("href", "")
            url = urljoin("https://www.oliveyoung.co.kr", href)

        # 카테고리
        category = _classify_oy_category(name, brand)
        is_pick = event_type == "pick_special"

        return {
            "name": name,
            "brand": brand or None,
            "original_price": original_price,
            "sale_price": sale_price,
            "discount_rate": discount_rate,
            "event_type": event_type,
            "category": category,
            "url": url or None,
            "image_url": image_url or None,
            "is_oliveyoung_pick": is_pick,
            "start_date": None,
            "end_date": None,
        }

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

        async with async_session() as session:
            saved = 0
            for item in items:
                stmt = sqlite_insert(OliveyoungDeal).values(**item)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["name", "brand", "event_type"],
                    set_={
                        "original_price": stmt.excluded.original_price,
                        "sale_price": stmt.excluded.sale_price,
                        "discount_rate": stmt.excluded.discount_rate,
                        "category": stmt.excluded.category,
                        "image_url": stmt.excluded.image_url,
                        "is_oliveyoung_pick": stmt.excluded.is_oliveyoung_pick,
                        "crawled_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                saved += 1

            await session.commit()
            return saved
