"""쿠팡 골드박스 크롤러 (coupang.com/np/goldbox).

매일 오전 7시 갱신되는 타임딜/골드박스 상품 수집.
curl_cffi Chrome TLS 핑거프린트로 봇차단 우회,
실패 시 Playwright headless fallback.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import CoupangDeal

logger = logging.getLogger("geojisekki.crawler.coupang")

BASE_URL = "https://www.coupang.com"
GOLDBOX_URL = f"{BASE_URL}/np/goldbox"

# 키워드 기반 카테고리 분류
CATEGORY_KEYWORDS = {
    "전자제품": ["노트북", "맥북", "아이패드", "갤럭시", "아이폰", "에어팟", "버즈", "모니터",
                "키보드", "마우스", "SSD", "TV", "로봇청소기", "건조기", "세탁기", "냉장고",
                "이어폰", "헤드폰", "충전기", "보조배터리", "태블릿", "워치", "카메라"],
    "식품": ["치킨", "커피", "음료", "과자", "라면", "고기", "쌀", "밀키트", "빵",
            "견과", "물", "우유", "즙", "차", "캡슐커피"],
    "패션": ["신발", "나이키", "아디다스", "뉴발란스", "자켓", "패딩", "운동화", "가방",
            "티셔츠", "바지", "원피스", "코트"],
    "뷰티": ["스킨", "로션", "세럼", "마스크팩", "선크림", "화장품", "향수", "샴푸",
            "클렌징", "에센스", "크림"],
    "생활용품": ["세제", "휴지", "물티슈", "칫솔", "치약", "세탁", "주방", "욕실",
              "수건", "행주", "쓰레기봉투"],
    "유아동": ["기저귀", "분유", "젖병", "장난감", "유아", "아기"],
    "건강": ["비타민", "유산균", "오메가", "영양제", "프로틴", "마스크"],
}


def _classify_category(name: str) -> Optional[str]:
    """키워드 매칭으로 카테고리 분류."""
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "기타"


def _parse_price(text: str) -> Optional[int]:
    """가격 텍스트에서 숫자 추출."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


class CoupangCrawler(BaseCrawler):
    name = "coupang"
    min_expected_items = 5
    max_pages = 1  # 골드박스는 단일 페이지

    async def crawl(self) -> list[dict]:
        """curl_cffi로 골드박스 크롤링, 실패 시 Playwright fallback."""
        try:
            items = await self._crawl_curl_cffi()
            if items:
                return items
        except ImportError:
            logger.warning("[coupang] curl_cffi 미설치 — Playwright fallback")
        except Exception as e:
            logger.warning("[coupang] curl_cffi 실패: %s — Playwright fallback", e)

        try:
            items = await self._crawl_playwright()
        except Exception as e:
            logger.error("[coupang] Playwright도 실패: %s", e)
            raise

        return items

    async def _crawl_curl_cffi(self) -> list[dict]:
        """curl_cffi Chrome TLS 핑거프린트로 골드박스 크롤링."""
        from curl_cffi import requests as cf_requests

        response = cf_requests.get(
            GOLDBOX_URL,
            impersonate="chrome120",
            headers={
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=30,
        )
        response.raise_for_status()
        items = self._parse_goldbox(response.text)
        logger.info("[coupang] curl_cffi: %d개 수집", len(items))
        return items

    async def _crawl_playwright(self) -> list[dict]:
        """Playwright headless 브라우저로 골드박스 크롤링."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="ko-KR",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            await page.goto(GOLDBOX_URL, wait_until="networkidle", timeout=60000)
            # 스크롤 다운으로 lazy load 트리거
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(500)

            html = await page.content()
            await browser.close()

        items = self._parse_goldbox(html)
        logger.info("[coupang] playwright: %d개 수집", len(items))
        return items

    def _parse_goldbox(self, html: str) -> list[dict]:
        """골드박스 페이지 HTML 파싱."""
        soup = BeautifulSoup(html, "lxml")
        items = []
        seen_urls: set[str] = set()

        # 골드박스 상품 카드 셀렉터들 (쿠팡 구조 변경 대비 다중 시도)
        product_cards = (
            soup.select("a.goldbox-item, a.goldbox-link")
            or soup.select("ul.goldbox-list li a")
            or soup.select("div.goldbox-content-container a[href*='/vp/products/']")
            or soup.select("a[href*='/vp/products/']")
        )

        for card in product_cards:
            try:
                item = self._parse_card(card)
                if item and item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    items.append(item)
            except Exception as e:
                logger.debug("[coupang] 카드 파싱 실패: %s", e)

        return items

    def _parse_card(self, card: BeautifulSoup) -> Optional[dict]:
        """개별 상품 카드 파싱."""
        # URL
        href = card.get("href", "")
        if not href or "/vp/products/" not in href:
            return None
        url = urljoin(BASE_URL, href)

        # 상품명
        name_el = (
            card.select_one(".product-title, .title, .name")
            or card.select_one("[class*='title'], [class*='name']")
        )
        name = name_el.get_text(strip=True) if name_el else ""
        if not name or len(name) < 3:
            # card 자체의 텍스트에서 추출 시도
            texts = [t.strip() for t in card.stripped_strings if len(t.strip()) > 5]
            name = texts[0] if texts else ""
        if not name or len(name) < 3:
            return None

        # 가격 (할인가)
        sale_el = (
            card.select_one(".sale-price, .price-value, .discount-price")
            or card.select_one("[class*='sale'], [class*='discount-price']")
        )
        sale_price = _parse_price(sale_el.get_text()) if sale_el else None

        # 원가
        original_el = (
            card.select_one(".base-price, .origin-price, .original-price")
            or card.select_one("[class*='base-price'], [class*='origin']")
        )
        original_price = _parse_price(original_el.get_text()) if original_el else None

        # 할인율
        discount_rate = None
        discount_el = (
            card.select_one(".discount-percentage, .discount-rate, .sale-ratio")
            or card.select_one("[class*='discount'], [class*='rate']")
        )
        if discount_el:
            rate_match = re.search(r"(\d+)", discount_el.get_text())
            if rate_match:
                discount_rate = int(rate_match.group(1))

        # 할인율 계산 (텍스트에서 못 찾았으면)
        if discount_rate is None and original_price and sale_price and original_price > sale_price:
            discount_rate = round((1 - sale_price / original_price) * 100)

        # 이미지
        img_el = card.select_one("img")
        image_url = ""
        if img_el:
            image_url = img_el.get("src", "") or img_el.get("data-src", "") or img_el.get("data-img-src", "")
        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        # 로켓배송 여부
        is_rocket = bool(card.select_one("[class*='rocket'], .delivery-rocket, img[alt*='로켓']"))

        # 카테고리 분류
        category = _classify_category(name)

        return {
            "name": name,
            "original_price": original_price,
            "sale_price": sale_price,
            "discount_rate": discount_rate,
            "category": category,
            "url": url,
            "image_url": image_url or None,
            "is_rocket": is_rocket,
        }

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

        crawl_started = datetime.utcnow()
        async with async_session() as session:
            saved = 0
            for item in items:
                stmt = sqlite_insert(CoupangDeal).values(**item)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["url"],
                    set_={
                        "name": stmt.excluded.name,
                        "original_price": stmt.excluded.original_price,
                        "sale_price": stmt.excluded.sale_price,
                        "discount_rate": stmt.excluded.discount_rate,
                        "category": stmt.excluded.category,
                        "image_url": stmt.excluded.image_url,
                        "is_rocket": stmt.excluded.is_rocket,
                        "crawled_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                saved += 1

            # 이번 크롤에 없던 상품 삭제 (만료된 골드박스)
            result = await session.execute(
                delete(CoupangDeal).where(
                    CoupangDeal.crawled_at < crawl_started,
                )
            )
            deleted = result.rowcount
            if deleted:
                logger.info("[coupang] stale 항목 %d개 삭제", deleted)

            await session.commit()
            return saved
