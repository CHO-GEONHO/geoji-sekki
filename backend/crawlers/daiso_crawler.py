"""다이소 가성비템 크롤러 (daiso.co.kr).

크롤링 주기: 월 2회 (1일, 15일) 07:00
대상: 메인 페이지에 노출된 최신 시즌/시리즈 컬렉션
전략: daiso.co.kr/brand/product/season/{id} 페이지 — 정적 HTML 크롤링 가능
AI: 가성비 점수 + 한줄 코멘트 배치 처리
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import DaisoProduct
from backend.services.llm_service import llm_service

logger = logging.getLogger("geojisekki.crawler.daiso")

BASE_URL = "https://www.daiso.co.kr"
MAIN_URL = f"{BASE_URL}/"

CATEGORY_KEYWORDS = {
    "생활용품": ["수납", "청소", "세탁", "정리", "걸이", "수건", "바구니", "박스", "타월", "거실화", "매트"],
    "주방": ["주방", "접시", "컵", "그릇", "수저", "밀폐", "냄비", "프라이팬", "도마"],
    "문구": ["문구", "펜", "노트", "스티커", "테이프", "가위", "풀", "클립"],
    "뷰티": ["화장", "미용", "브러쉬", "퍼프", "거울", "화장솜", "면봉", "헤어"],
    "식품": ["과자", "음료", "커피", "차", "젤리", "사탕", "초콜릿"],
    "전자": ["충전", "케이블", "이어폰", "보조배터리", "USB", "LED", "건전지"],
    "인테리어": ["인테리어", "조명", "액자", "화분", "캔들", "디퓨저"],
    "패션잡화": ["양말", "장갑", "모자", "가방", "파우치", "지갑"],
    "계절/스포츠": ["봄", "여름", "가을", "겨울", "스포츠", "캠핑", "아웃도어"],
}


def _get_month_key(d: Optional[date] = None) -> str:
    d = d or date.today()
    return d.strftime("%Y-%m")


def _classify_daiso_category(name: str) -> str:
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "기타"


def _parse_slide(slide: BeautifulSoup, season_url: str) -> list[dict]:
    """swiper-slide 하나에서 상품 파싱.

    텍스트 형식: {상품명}_{상품ID}_{가격}원
    여러 상품은 '/' 구분. 색상/사이즈 변형은 첫 번째만 추출.
    """
    p_el = slide.select_one("p")
    img_el = slide.select_one("div.pic img")
    if not p_el:
        return []

    text = p_el.get_text(strip=True)
    image_url = ""
    if img_el:
        src = img_el.get("src", "")
        if src and not src.startswith("http"):
            src = urljoin(BASE_URL, src)
        image_url = src

    products = []
    for part in text.split("/"):
        part = part.strip()
        segments = part.split("_")
        if len(segments) < 3:
            continue
        # 마지막 세그먼트가 가격 (숫자 + 원)
        if not re.search(r"\d+원", segments[-1]):
            continue
        price_text = segments[-1]
        price = int(re.sub(r"[^\d]", "", price_text) or 0)
        name = "_".join(segments[:-2]).strip()
        # 이름이 한글/영문으로 시작 (숫자 시작 = 같은 상품 다른 사이즈 variant → 스킵)
        if not name or not re.match(r"^[가-힣a-zA-Z]", name):
            continue
        if price <= 0 or price > 10000:
            continue
        products.append({
            "name": name,
            "price": price,
            "image_url": image_url or None,
            "url": season_url,
        })

    return products


class DaisoCrawler(BaseCrawler):
    name = "daiso"
    min_expected_items = 10

    async def crawl(self) -> list[dict]:
        """daiso.co.kr 메인 페이지에서 최신 시즌 컬렉션을 찾아 상품 수집."""
        season_urls = await self._get_season_urls()
        if not season_urls:
            logger.warning("[daiso] 시즌 URL을 찾지 못했습니다.")
            return []

        items = []
        for url in season_urls:
            try:
                page_items = await self._crawl_season(url)
                items.extend(page_items)
                logger.info("[daiso] %s: %d개 수집", url.split("/")[-1], len(page_items))
                await self.delay()
            except Exception as e:
                logger.error("[daiso] %s 크롤링 실패: %s", url, e)

        # 중복 상품명 제거 (같은 달에 중복 가능)
        seen_names = set()
        unique_items = []
        for item in items:
            if item["name"] not in seen_names:
                seen_names.add(item["name"])
                unique_items.append(item)
        items = unique_items

        # AI 가성비 점수 (배치)
        items = await self._score_items(items)
        return items

    async def _get_season_urls(self) -> list[str]:
        """메인 페이지에서 최신 시즌 URL 목록 추출 (최대 3개)."""
        try:
            html = await self.fetch(MAIN_URL)
            soup = BeautifulSoup(html, "lxml")
            seen_ids: set[int] = set()
            urls = []
            for a in soup.select("a[href*='/brand/product/season/']"):
                href = a.get("href", "")
                m = re.search(r"/season/(\d+)", href)
                if m:
                    sid = int(m.group(1))
                    if sid not in seen_ids:
                        seen_ids.add(sid)
                        full_url = urljoin(BASE_URL, href)
                        urls.append((sid, full_url))

            # 최신 6개 크롤링
            urls.sort(reverse=True)
            return [u for _, u in urls[:6]]
        except Exception as e:
            logger.error("[daiso] 메인 페이지 파싱 실패: %s", e)
            return []

    async def _crawl_season(self, season_url: str) -> list[dict]:
        """시즌 페이지 크롤링."""
        html = await self.fetch(season_url)
        soup = BeautifulSoup(html, "lxml")
        month_key = _get_month_key()

        # 시즌명
        h3 = soup.select_one("section.section-product h3 strong")
        season_name = h3.get_text(strip=True) if h3 else ""

        slides = soup.select("div.swiper-board .swiper-slide")
        products = []
        for idx, slide in enumerate(slides):
            for product in _parse_slide(slide, season_url):
                product["category"] = _classify_daiso_category(product["name"])
                product["is_new"] = True
                product["ranking"] = idx + 1
                product["ai_score"] = None
                product["ai_comment"] = None
                product["month_key"] = month_key
                products.append(product)

        return products

    async def _score_items(self, items: list[dict]) -> list[dict]:
        """AI 가성비 점수 배치 처리 (20개씩)."""
        if not items:
            return items

        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "prompts" / "daiso_score.txt"
            system_prompt = prompt_path.read_text(encoding="utf-8")

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

        current_month = items[0]["month_key"]  # 이번 크롤의 month_key
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

            # 지난 달 다이소 데이터 삭제
            result = await session.execute(
                delete(DaisoProduct).where(DaisoProduct.month_key < current_month)
            )
            deleted = result.rowcount
            if deleted:
                logger.info("[daiso] 이전 월 stale 항목 %d개 삭제", deleted)

            await session.commit()
            return saved
