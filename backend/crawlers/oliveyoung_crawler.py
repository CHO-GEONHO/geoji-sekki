"""올리브영 세일/베스트 크롤러 (oliveyoung.co.kr).

curl_cffi로 Cloudflare를 브라우저 TLS 핑거프린트 모방하여 우회.
httpx는 Cloudflare JS 챌린지에 막힘 → curl_cffi(impersonate="chrome131") 사용.

크롤링 주기: 주 2회 (월/목) 07:00
대상: 전체 판매 랭킹 베스트 (100위) — 할인율, 이벤트 배지 포함
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import OliveyoungDeal

logger = logging.getLogger("geojisekki.crawler.oliveyoung")

BEST_URL = (
    "https://www.oliveyoung.co.kr/store/main/getBestList.do"
    "?dispCatNo=900000100100001&fltDispCatNo=&prdSort=01"
)

# 카테고리 분류 (data-ref-goodscategory 또는 상품명 기반)
CATEGORY_MAP = {
    "스킨케어": ["스킨", "토너", "에센스", "세럼", "크림", "로션", "앰플", "마스크팩", "시트팩", "클렌징"],
    "메이크업": ["파운데이션", "립", "아이", "블러셔", "쿠션", "틴트", "마스카라", "베이스"],
    "헤어": ["샴푸", "트리트먼트", "헤어", "린스", "헤어에센스"],
    "바디": ["바디", "핸드크림", "바디워시", "로션", "선크림", "선케어"],
    "건강": ["비타민", "유산균", "오메가", "콜라겐", "프로바이오틱스", "영양제", "건강기능"],
    "향수": ["향수", "퍼퓸", "오드"],
    "남성": ["남성", "맨즈", "쉐이빙"],
}


def _classify_oy_category(name: str, brand: str = "", raw_cat: str = "") -> str:
    """카테고리 분류 (페이지 제공 카테고리 우선, 없으면 키워드 매칭)."""
    if raw_cat:
        # "01 > 마스크팩 > 시트팩" 형태에서 중분류 추출
        parts = [p.strip() for p in raw_cat.split(">")]
        middle = parts[1] if len(parts) > 1 else ""
        for category, keywords in CATEGORY_MAP.items():
            for kw in keywords:
                if kw in middle:
                    return category

    text = f"{name} {brand}".lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in text:
                return category
    return "기타"


def _parse_price(text: str) -> Optional[int]:
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else None


class OliveyoungCrawler(BaseCrawler):
    name = "oliveyoung"
    min_expected_items = 20

    async def crawl(self) -> list[dict]:
        """curl_cffi로 Cloudflare 우회, 베스트셀러 상품 크롤링."""
        try:
            items = await self._crawl_curl_cffi()
            if items:
                return items
        except ImportError:
            logger.warning("[oliveyoung] curl_cffi 미설치 — Playwright fallback")
        except Exception as e:
            logger.warning("[oliveyoung] curl_cffi 실패: %s — Playwright fallback", e)

        # Fallback: Playwright
        try:
            items = await self._crawl_playwright()
        except Exception as e:
            logger.error("[oliveyoung] Playwright도 실패: %s", e)
            raise

        return items

    async def _crawl_curl_cffi(self) -> list[dict]:
        """curl_cffi (Chrome TLS 핑거프린트 모방) 크롤링."""
        from curl_cffi import requests as cf_requests

        response = cf_requests.get(
            BEST_URL,
            impersonate="chrome131",
            headers={"Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        products = self._parse_products(soup)
        logger.info("[oliveyoung] curl_cffi 수집: %d개", len(products))
        return products

    async def _crawl_playwright(self) -> list[dict]:
        """Playwright headless fallback (stealth 설정 적용)."""
        from playwright.async_api import async_playwright

        items = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
            )
            # webdriver 감지 우회
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )

            page = await context.new_page()
            try:
                await page.goto(BEST_URL, wait_until="domcontentloaded", timeout=30000)
                # 상품이 로드될 때까지 대기
                try:
                    await page.wait_for_selector(".prd_info", timeout=10000)
                except Exception:
                    pass
                # 스크롤로 lazy load 트리거
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(800)

                html = await page.content()
                soup = BeautifulSoup(html, "lxml")
                items = self._parse_products(soup)
                logger.info("[oliveyoung] Playwright 수집: %d개", len(items))
            except Exception as e:
                logger.error("[oliveyoung] Playwright 페이지 실패: %s", e)
            finally:
                await browser.close()

        return items

    def _parse_products(self, soup: BeautifulSoup) -> list[dict]:
        """HTML에서 상품 목록 파싱."""
        cards = soup.select("div.prd_info, li.prd_info")
        products = []
        for rank, card in enumerate(cards, start=1):
            try:
                product = self._parse_single(card, rank)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[oliveyoung] 상품 파싱 실패: %s", e)
        return products

    def _parse_single(self, card: BeautifulSoup, rank: int) -> Optional[dict]:
        """단일 상품 카드 파싱."""
        # 상품명
        name_el = card.select_one(".tx_name, p.prd_name, .prd_name a")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        # 브랜드
        brand_el = card.select_one(".tx_brand")
        brand = brand_el.get_text(strip=True) if brand_el else ""

        # 정가
        org_el = card.select_one(".tx_org .tx_num")
        original_price = _parse_price(org_el.get_text(strip=True)) if org_el else None

        # 할인가
        cur_el = card.select_one(".tx_cur .tx_num")
        if not cur_el:
            return None
        sale_price = _parse_price(cur_el.get_text(strip=True))
        if not sale_price:
            return None

        # 할인율 계산
        discount_rate = None
        if original_price and sale_price and original_price > sale_price:
            discount_rate = round((1 - sale_price / original_price) * 100)

        # 이벤트 배지 (세일, 1+1, 쿠폰 등)
        flags = [f.get_text(strip=True) for f in card.select(".icon_flag")]
        event_type = "best"
        for flag in flags:
            if "1+1" in flag:
                event_type = "1+1"
                break
            elif "2+1" in flag:
                event_type = "2+1"
                break
            elif "세일" in flag:
                event_type = "sale"
                break

        # 이미지
        img_el = card.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""

        # URL
        link_el = card.select_one("a.prd_thumb, a[href*='getGoodsDetail']")
        url = link_el.get("href", "") if link_el else ""
        if url and not url.startswith("http"):
            url = urljoin("https://www.oliveyoung.co.kr", url)

        # 카테고리 (data-ref-goodscategory 활용)
        cat_btn = card.select_one("[data-ref-goodscategory]")
        raw_cat = cat_btn.get("data-ref-goodscategory", "") if cat_btn else ""
        category = _classify_oy_category(name, brand, raw_cat)

        is_pick = event_type in ("1+1", "2+1")

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
