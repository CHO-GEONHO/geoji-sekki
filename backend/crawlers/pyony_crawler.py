"""편의점 4사 행사 상품 크롤러 (pyony.com).

pyony.com robots.txt 확인일: 2026-03-13 — 크롤링 제한 없음.
소스: https://pyony.com
대안 소스: martmonster.com (사전 조사 완료, 구조 유사)
"""

import logging
import re
from datetime import datetime, date

from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import CvsProduct

logger = logging.getLogger("geojisekki.crawler.pyony")

# 편의점별 URL 매핑
STORE_URLS = {
    "cu": "https://pyony.com/brands/cu/",
    "gs25": "https://pyony.com/brands/gs25/",
    "seven": "https://pyony.com/brands/seveneleven/",
    "emart24": "https://pyony.com/brands/emart24/",
}

# 행사 타입 매핑
EVENT_TYPE_MAP = {
    "1+1": "1+1",
    "2+1": "2+1",
    "3+1": "3+1",
    "할인": "discount",
    "덤증정": "bonus",
}

# 카테고리 키워드 매핑
CATEGORY_KEYWORDS = {
    "음료": ["물", "주스", "커피", "차", "탄산", "이온", "에너지", "우유", "두유", "식혜",
             "콜라", "사이다", "핫식스", "몬스터", "레드불", "게토레이", "포카리"],
    "과자": ["과자", "스낵", "칩", "쿠키", "비스킷", "초콜릿", "사탕", "젤리", "껌",
             "프링글스", "포카칩", "새우깡", "꼬깔콘"],
    "간편식사": ["도시락", "삼각김밥", "샌드위치", "햄버거", "컵밥", "김밥", "라면",
                "즉석", "냉동", "만두", "피자", "핫도그", "떡볶이"],
    "아이스크림": ["아이스크림", "빙과", "바", "콘", "모나카", "빙수", "하겐다즈",
                  "베스킨", "메로나", "보석바", "수박바", "누가바"],
    "생활용품": ["휴지", "세제", "칫솔", "치약", "샴푸", "바디", "마스크", "물티슈",
                "건전지", "충전", "케이블"],
    "유제품": ["요거트", "요구르트", "치즈", "버터", "크림"],
}


def _get_week_key(d: date | None = None) -> str:
    """ISO 주차 키 생성 (e.g. '2026-W11')"""
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _classify_category(name: str) -> str:
    """상품명 기반 카테고리 분류"""
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "기타"


def _calc_unit_price(price: int, event_type: str) -> int:
    """행사 타입에 따른 개당 실질 가격 계산"""
    if event_type == "1+1":
        return price // 2
    elif event_type == "2+1":
        return (price * 2) // 3
    elif event_type == "3+1":
        return (price * 3) // 4
    return price


class PyonyCrawler(BaseCrawler):
    name = "pyony"
    min_expected_items = 50

    async def crawl(self) -> list[dict]:
        items = []
        for store, url in STORE_URLS.items():
            try:
                store_items = await self._crawl_store(store, url)
                items.extend(store_items)
                logger.info("[pyony] %s: %d개 수집", store, len(store_items))
                await self.delay()
            except Exception as e:
                logger.error("[pyony] %s 크롤링 실패: %s", store, e)
        return items

    async def _crawl_store(self, store: str, base_url: str) -> list[dict]:
        """한 편의점의 전체 행사 상품 크롤링 (페이지네이션 포함)"""
        items = []
        page = 1

        while True:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            html = await self.fetch(url)
            soup = BeautifulSoup(html, "lxml")

            products = self._parse_products(soup, store)
            if not products:
                break

            items.extend(products)
            page += 1

            # 다음 페이지 존재 확인
            next_link = soup.select_one("a.next, .pagination a[rel='next']")
            if not next_link:
                break

            await self.delay()

        return items

    def _parse_products(self, soup: BeautifulSoup, store: str) -> list[dict]:
        """HTML에서 상품 목록 파싱"""
        products = []
        week_key = _get_week_key()

        # pyony.com 상품 카드 셀렉터
        cards = soup.select(".product-list .product-item, .card-list .card")

        for card in cards:
            try:
                product = self._parse_single_product(card, store, week_key)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[pyony] 상품 파싱 실패: %s", e)

        return products

    def _parse_single_product(
        self, card: BeautifulSoup, store: str, week_key: str
    ) -> dict | None:
        """단일 상품 카드 파싱"""
        # 상품명
        name_el = card.select_one(".product-name, .card-title, h3, h4")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        # 가격
        price_el = card.select_one(".product-price, .price, .card-price")
        price_text = price_el.get_text(strip=True) if price_el else "0"
        price = int(re.sub(r"[^\d]", "", price_text) or "0")
        if price <= 0 or price > 1_000_000:
            return None

        # 행사 타입
        event_el = card.select_one(".badge, .event-type, .tag, .label")
        event_text = event_el.get_text(strip=True) if event_el else ""
        event_type = "discount"
        for key, val in EVENT_TYPE_MAP.items():
            if key in event_text:
                event_type = val
                break

        # 이미지
        img_el = card.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""
        if image_url and not image_url.startswith("http"):
            image_url = f"https://pyony.com{image_url}"

        # 카테고리 분류
        category = _classify_category(name)
        unit_price = _calc_unit_price(price, event_type)

        return {
            "store": store,
            "name": name,
            "price": price,
            "event_type": event_type,
            "category": category,
            "unit_price": unit_price,
            "image_url": image_url or None,
            "start_date": None,
            "end_date": None,
            "week_key": week_key,
        }

    async def save(self, items: list[dict]) -> int:
        """DB 저장 (INSERT OR REPLACE)"""
        if not items:
            return 0

        async with async_session() as session:
            saved = 0
            for item in items:
                stmt = sqlite_insert(CvsProduct).values(**item)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["store", "name", "week_key"],
                    set_={
                        "price": stmt.excluded.price,
                        "event_type": stmt.excluded.event_type,
                        "category": stmt.excluded.category,
                        "unit_price": stmt.excluded.unit_price,
                        "image_url": stmt.excluded.image_url,
                        "crawled_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                saved += 1

            await session.commit()
            return saved
