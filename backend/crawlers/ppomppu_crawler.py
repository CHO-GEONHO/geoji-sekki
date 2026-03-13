"""뽐뿌 핫딜 크롤러 (ppomppu.co.kr).

ppomppu.co.kr robots.txt 확인일: 2026-03-13
크롤링 범위: 핫딜 게시판 1~2페이지, 일 2회
요청 간 2~5초 랜덤 딜레이 적용
"""

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.crawlers.base import BaseCrawler
from backend.database import async_session
from backend.models import Hotdeal
from backend.services.llm_service import llm_service

logger = logging.getLogger("geojisekki.crawler.ppomppu")

BASE_URL = "https://www.ppomppu.co.kr"
HOTDEAL_URL = f"{BASE_URL}/zboard/zboard.php?id=ppomppu"

# 키워드 기반 카테고리 분류 (LLM 호출 최소화)
CATEGORY_KEYWORDS = {
    "전자제품": ["노트북", "맥북", "아이패드", "갤럭시", "아이폰", "에어팟", "버즈", "모니터",
                "키보드", "마우스", "SSD", "그래픽카드", "태블릿", "워치", "이어폰", "헤드폰",
                "충전기", "보조배터리", "TV", "로봇청소기", "건조기", "세탁기", "냉장고"],
    "식품": ["치킨", "피자", "커피", "음료", "과자", "라면", "배달", "맥주", "소주",
            "고기", "쌀", "밀키트", "도시락", "빵"],
    "패션": ["신발", "나이키", "아디다스", "뉴발란스", "자켓", "패딩", "운동화", "가방",
            "지갑", "벨트", "옷", "티셔츠", "청바지"],
    "뷰티": ["스킨", "로션", "세럼", "마스크팩", "선크림", "화장품", "향수", "샴푸",
            "올리브영"],
    "생활용품": ["세제", "휴지", "물티슈", "칫솔", "치약", "세탁", "주방", "욕실"],
    "여행": ["항공", "호텔", "숙박", "여행", "렌터카", "비행기", "리조트"],
    "도서/문화": ["책", "공연", "영화", "넷플릭스", "유튜브", "게임", "스팀", "콘솔",
                 "플스", "닌텐도", "스위치"],
}


def _classify_by_keyword(title: str) -> str | None:
    """키워드 매칭으로 카테고리 분류 (80% 커버)"""
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return None


def _parse_price(text: str) -> int | None:
    """가격 텍스트에서 숫자 추출"""
    if not text:
        return None
    # "123,456원" or "123456" 패턴
    numbers = re.findall(r"[\d,]+", text.replace(",", ""))
    if numbers:
        try:
            return int(numbers[0].replace(",", ""))
        except ValueError:
            return None
    return None


class PpomppuCrawler(BaseCrawler):
    name = "ppomppu"
    min_expected_items = 5
    max_pages = 2  # 1~2페이지만

    async def crawl(self) -> list[dict]:
        items = []
        for page in range(1, self.max_pages + 1):
            url = f"{HOTDEAL_URL}&page={page}"
            try:
                html = await self.fetch(url)
                page_items = self._parse_page(html)
                items.extend(page_items)
                logger.info("[ppomppu] page %d: %d개 수집", page, len(page_items))
                if page < self.max_pages:
                    await self.delay()
            except Exception as e:
                logger.error("[ppomppu] page %d 크롤링 실패: %s", page, e)

        # AI 분류 (키워드 매칭 실패한 아이템만)
        items = await self._classify_items(items)
        return items

    def _parse_page(self, html: str) -> list[dict]:
        """핫딜 게시판 페이지 파싱"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 뽐뿌 게시판 행 셀렉터
        rows = soup.select("tr.common-list0, tr.common-list1, tr[class*='list']")

        for row in rows:
            try:
                item = self._parse_row(row)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug("[ppomppu] 행 파싱 실패: %s", e)

        return items

    def _parse_row(self, row: BeautifulSoup) -> dict | None:
        """게시글 행 파싱"""
        # 제목
        title_el = row.select_one("a.title, td.title a, a.baseList-title")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # URL
        href = title_el.get("href", "")
        url = urljoin(BASE_URL, href) if href else ""
        if not url:
            return None

        # 추천수
        vote_el = row.select_one(".vote, .baseList-rec, td.recommend .symph_count")
        vote_text = vote_el.get_text(strip=True) if vote_el else "0"
        vote_count = int(re.sub(r"[^\d\-]", "", vote_text) or "0")

        # 댓글수
        comment_el = row.select_one(".comment_count, .baseList-comment")
        comment_text = comment_el.get_text(strip=True) if comment_el else "0"
        comment_count = int(re.sub(r"[^\d]", "", comment_text) or "0")

        # 가격 (제목에서 추출 시도)
        price_value = _parse_price(title)

        # 이미지
        img_el = row.select_one("img.thumb, img")
        image_url = img_el.get("src", "") if img_el else ""
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(BASE_URL, image_url)

        # 작성 시간
        date_el = row.select_one(".date, .baseList-date, td.time")
        posted_at = None
        if date_el:
            date_text = date_el.get_text(strip=True)
            try:
                if ":" in date_text and len(date_text) <= 5:
                    posted_at = datetime.now().replace(
                        hour=int(date_text.split(":")[0]),
                        minute=int(date_text.split(":")[1]),
                        second=0, microsecond=0,
                    )
                else:
                    posted_at = datetime.strptime(date_text[:10], "%Y-%m-%d")
            except (ValueError, IndexError):
                pass

        # 키워드 기반 카테고리 분류
        category = _classify_by_keyword(title)

        return {
            "source": "ppomppu",
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
            "image_url": image_url or None,
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

            # 결과 매핑
            class_map = {c["id"]: c for c in classified}
            for idx, item in enumerate(items):
                if idx in class_map:
                    item["category"] = class_map[idx].get("category", "기타")
                    item["summary"] = class_map[idx].get("summary")

        except Exception as e:
            logger.warning("[ppomppu] AI 분류 실패, 기타로 처리: %s", e)
            for item in items:
                if item["category"] is None:
                    item["category"] = "기타"

        return items

    async def save(self, items: list[dict]) -> int:
        if not items:
            return 0

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

            await session.commit()
            return saved
