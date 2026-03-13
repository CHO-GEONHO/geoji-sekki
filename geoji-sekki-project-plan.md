# 거지세끼 (GeojiSekki) — 프로젝트 기획서 v1.0

> **"세 끼 아끼는 게 곧 실력이다"**
> 매일 들어오는 절약 정보 큐레이션 앱

**작성일**: 2026-03-13
**작성자**: 조건호 (건호)
**상태**: 기획 완료 → MVP 개발 착수 전

---

## 1. 프로젝트 개요

### 1.1 컨셉
- 편의점 행사, 올리브영 세일, 다이소 가성비템, 커뮤니티 핫딜 정보를 **하나의 앱에서 AI 큐레이션**으로 제공
- 타겟: 20대~30대 초반, 절약/재테크에 관심 있는 MZ세대
- 톤앤매너: "자랑스러운 거지" — 짧고, 구어체, 약간 건방진 톤
- 포지션: 기존 앱들은 한 영역만 다룸 (폴센트=쿠팡, 편의점알리미=편의점). 거지세끼는 **생활 전반 절약 정보를 크로스로 큐레이션**

### 1.2 차별화 포인트
- 편의점 4사 **크로스 비교** (같은 상품 어디가 싸냐)
- 여러 소스(편의점/올영/다이소/커뮤니티)를 **하나의 피드**로 통합
- AI가 매일 "오늘의 절약 피드"를 자동 생성
- 향후 개인화 알고리즘으로 사용자 맞춤 추천

### 1.3 수익화 방향 (향후)
- 쿠팡 파트너스 / 올리브영 제휴 링크 수수료 (CPA)
- 카드사 제휴 (카드 발급 CPA) — 3차 확장
- 앱 내 네이티브 광고 (절약 관련 서비스 광고)
- 프리미엄 기능 (개인화 추천, 푸시 알림)

---

## 2. 기술 스택

### 2.1 백엔드
| 항목 | 선택 | 이유 |
|------|------|------|
| 프레임워크 | FastAPI (Python 3.11+) | 운명서 동일 스택, 비동기 크롤링 |
| DB | SQLite + SQLAlchemy | 초기 MVP 충분, 맥미니 로컬 |
| LLM | DeepSeek V3.2 (`deepseek-chat`) | 비용 효율 (input $0.28/1M), OpenAI SDK 호환 |
| 크롤링 | httpx + BeautifulSoup4 | 정적 페이지 위주, 가벼움 |
| 동적 크롤링 | Playwright (필요 시) | 올리브영 등 JS 렌더링 필요한 경우 |
| 스케줄러 | APScheduler | FastAPI 내장 스케줄링 |
| 캐싱 | 파일 기반 JSON 캐시 | 심플, SQLite 백업 |

### 2.2 프론트엔드
| 항목 | 선택 | 이유 |
|------|------|------|
| 프레임워크 | Vite + React 18 | 운명서 동일, 빠른 개발 |
| 스타일링 | Tailwind CSS | 유틸리티 기반, 빠른 UI |
| 상태관리 | Zustand | 가볍고 직관적 |
| HTTP 클라이언트 | axios + React Query | 캐싱, 리패칭 자동화 |
| 라우팅 | React Router v6 | SPA 라우팅 |
| 아이콘 | Lucide React | 가볍고 깔끔 |

### 2.3 인프라
| 항목 | 선택 | 이유 |
|------|------|------|
| 서버 | Mac Mini M4 (기존) | 24/7 운영 중, 추가 비용 없음 |
| 도메인 | geojisekki.zzimong.com (또는 별도 도메인) | Cloudflare Tunnel 활용 |
| 리버스 프록시 | Cloudflare Tunnel | 기존 인프라 재활용 |
| CI/CD | OpenClaw 자동화 | 쿠로미/호타루 에이전트 |
| 모니터링 | Telegram 알림 (OpenClaw) | 크롤러 실패 시 즉시 알림 |

---

## 3. 데이터 소스 & 크롤링 전략

### 3.1 편의점 4사 행사 비교

**소스**: pyony.com (편의점 행사 정보 모음 사이트)
- robots.txt 크롤링 제한 없음 확인됨
- CU, GS25, 세븐일레븐, 이마트24 전부 커버
- 1+1, 2+1, 3+1, 할인 행사 포함
- 이미 다수의 프로젝트에서 중간 소스로 활용 중

**대안 소스**: 마트몬(martmonster.com), 편의점행사.com

**크롤링 방식**:
```
매주 월요일 06:00 KST → pyony.com 크롤링
  → 편의점별 행사 상품 파싱 (상품명, 가격, 행사타입, 카테고리)
  → SQLite 저장 (products 테이블)
  → 이전 주 데이터와 diff 비교
  → 신규/변경 상품 마킹
```

**핵심 가공**:
- 같은 상품이 여러 편의점에서 행사 중일 때 **크로스 비교** (어디가 더 싸냐)
- 카테고리별 "이번 주 가성비 TOP 5" AI 선정

**데이터 스키마**:
```sql
CREATE TABLE cvs_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store TEXT NOT NULL,          -- 'gs25', 'cu', 'seven', 'emart24'
    name TEXT NOT NULL,           -- 상품명
    price INTEGER NOT NULL,       -- 정가 (원)
    event_type TEXT NOT NULL,     -- '1+1', '2+1', '3+1', 'discount'
    category TEXT,                -- '음료', '과자', '간편식사', '생활용품', '아이스크림'
    unit_price INTEGER,           -- 개당 실질 가격 (계산값)
    image_url TEXT,               -- 상품 이미지 URL
    start_date DATE,              -- 행사 시작일
    end_date DATE,                -- 행사 종료일
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    week_key TEXT NOT NULL        -- '2026-W11' 형태의 주차 키
);

CREATE INDEX idx_cvs_week ON cvs_products(week_key);
CREATE INDEX idx_cvs_store ON cvs_products(store);
CREATE INDEX idx_cvs_category ON cvs_products(category);
```

### 3.2 뽐뿌 핫딜 TOP

**소스**: ppomppu.co.kr 핫딜 게시판
- 국내 최대 핫딜 커뮤니티
- 추천수 기반 정렬 가능

**크롤링 방식**:
```
매일 08:00, 18:00 KST → 뽐뿌 핫딜 게시판 크롤링
  → 최근 24시간 내 추천수 상위 게시글 파싱
  → 제목, 가격, 추천수, 원본 링크 저장
  → DeepSeek로 카테고리 자동 분류 + 한줄 요약
  → "오늘의 핫딜 TOP 5" 피드 생성
```

**데이터 스키마**:
```sql
CREATE TABLE hotdeals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,          -- 'ppomppu', 'fmkorea', 'clien' (향후 확장)
    title TEXT NOT NULL,
    price TEXT,                    -- 가격 텍스트 (파싱 전)
    price_value INTEGER,           -- 파싱된 가격 (원)
    original_price INTEGER,        -- 원래 가격 (할인율 계산용)
    discount_rate INTEGER,         -- 할인율 (%)
    vote_count INTEGER DEFAULT 0,  -- 추천수
    comment_count INTEGER DEFAULT 0,
    url TEXT NOT NULL,             -- 원본 링크
    category TEXT,                 -- AI 분류 카테고리
    summary TEXT,                  -- AI 한줄 요약
    image_url TEXT,
    posted_at DATETIME,
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hotdeals_date ON hotdeals(posted_at);
CREATE INDEX idx_hotdeals_votes ON hotdeals(vote_count DESC);
```

### 3.3 올리브영 세일/1+1

**소스**: oliveyoung.co.kr
- 세일 페이지: `/store/main/getSaleList.do`
- 랭킹 페이지: `/store/main/getBestList.do`
- 이벤트 페이지: 월별 올영데이, 올영세일

**크롤링 방식**:
```
주 2회 (월/목) 07:00 KST → 올리브영 세일 페이지 크롤링
  → 세일 상품명, 정가, 할인가, 할인율 파싱
  → 1+1, 올영픽 특가, 한정 기획 구분
  → 카테고리 분류 (스킨케어, 메이크업, 헤어, 바디, 건강)
  → "이번 주 올영 핫딜 TOP 5" AI 선정

올영세일 기간 (연 4회, 3/6/9/12월) → 크롤링 주기 일 1회로 증가
올영데이 (매월 25~27일) → 크롤링 주기 일 1회
```

**주의사항**:
- 올리브영은 JS 렌더링 기반 → Playwright 또는 모바일 API 확인 필요
- 대안: Octoparse 같은 도구 검토, 또는 올영 모바일 웹(m.oliveyoung.co.kr) 크롤링

**데이터 스키마**:
```sql
CREATE TABLE oliveyoung_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT,
    original_price INTEGER,
    sale_price INTEGER,
    discount_rate INTEGER,          -- 할인율 (%)
    event_type TEXT,                -- 'sale', '1+1', 'pick_special', 'limited'
    category TEXT,                  -- '스킨케어', '메이크업', '헤어', '바디', '건강'
    url TEXT,
    image_url TEXT,
    is_oliveyoung_pick BOOLEAN DEFAULT FALSE,
    start_date DATE,
    end_date DATE,
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_oy_date ON oliveyoung_deals(crawled_at);
CREATE INDEX idx_oy_category ON oliveyoung_deals(category);
CREATE INDEX idx_oy_discount ON oliveyoung_deals(discount_rate DESC);
```

### 3.4 다이소 가성비템

**소스**: daisomall.co.kr
- 신상품 페이지
- 카테고리별 랭킹 (베스트셀러)
- 매월 600+ 신상품 출시

**크롤링 방식**:
```
월 2회 (1일, 15일) 07:00 KST → 다이소몰 크롤링
  → 신상품 목록 파싱 (상품명, 가격, 카테고리)
  → 베스트셀러 랭킹 파싱
  → DeepSeek로 "가성비 추천" 점수 부여
  → "이번 달 다이소 가성비 TOP 10" 피드 생성
```

**데이터 스키마**:
```sql
CREATE TABLE daiso_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,        -- 1000, 2000, 3000, 5000
    category TEXT,                 -- '생활용품', '주방', '문구', '뷰티', '식품', '전자'
    is_new BOOLEAN DEFAULT FALSE,
    ranking INTEGER,               -- 베스트셀러 순위
    url TEXT,
    image_url TEXT,
    ai_score REAL,                 -- AI 가성비 추천 점수 (0~10)
    ai_comment TEXT,               -- AI 한줄 코멘트
    month_key TEXT NOT NULL,       -- '2026-03' 형태
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_daiso_month ON daiso_products(month_key);
CREATE INDEX idx_daiso_ranking ON daiso_products(ranking);
```

---

## 4. API 설계

### 4.1 엔드포인트

```
GET  /api/feed                    → 오늘의 데일리 피드 (AI 큐레이션 5~7개)
GET  /api/feed?date=2026-03-13    → 특정 날짜 피드

GET  /api/cvs                     → 편의점 행사 전체
GET  /api/cvs?store=gs25          → 특정 편의점 필터
GET  /api/cvs?category=음료       → 카테고리 필터
GET  /api/cvs?event=1+1           → 행사 타입 필터
GET  /api/cvs/compare?product=핫식스  → 편의점 간 가격 비교

GET  /api/hotdeals                → 핫딜 목록 (추천순)
GET  /api/hotdeals?limit=5        → TOP N

GET  /api/oliveyoung              → 올영 세일 상품
GET  /api/oliveyoung?category=스킨케어
GET  /api/oliveyoung/calendar     → 올영 세일 일정 캘린더

GET  /api/daiso                   → 다이소 가성비템
GET  /api/daiso?category=생활용품
GET  /api/daiso/new               → 이번 달 신상품

GET  /api/health                  → 서버 + 크롤러 상태
```

### 4.2 데일리 피드 생성 로직

```python
# 매일 07:00 KST 실행
async def generate_daily_feed():
    """
    1. 오늘 기준 활성 데이터 수집
       - 편의점: 이번 주 행사 상품 중 가성비 상위
       - 핫딜: 최근 24시간 추천수 상위
       - 올영: 현재 세일 진행 중 상품
       - 다이소: 이번 달 신상 + 베스트
    2. DeepSeek에 전체 데이터 + 프롬프트 전달
    3. "오늘의 거지세끼 피드" 5~7개 선정
    4. 거지세끼 톤으로 카피 생성
    5. SQLite feeds 테이블에 저장
    """
```

**DeepSeek 프롬프트 (피드 생성)**:
```
너는 "거지세끼" 앱의 AI 에디터야. 
20대가 매일 30초 훑어보는 절약 정보 피드를 만들어야 해.

톤 규칙:
- 반말, 구어체, 짧게 (2~3줄 이내)
- 핵심 숫자(가격, 할인율)는 꼭 포함
- "~각", "~ㄱㄱ", "~떴다" 같은 표현 자연스럽게 사용
- 거지력이 느껴지는 실용적인 팁 포함
- 이모지 적절히 사용 (1~2개)

오늘 수집된 데이터:
{collected_data_json}

위 데이터에서 가장 "맛있는" 정보 5~7개를 골라서,
각각 제목(1줄)과 본문(2~3줄) 형태로 작성해줘.

JSON 형태로만 응답:
[
  {
    "title": "핫식스 1+1 떴다 🔥",
    "body": "GS25 ㄱㄱ (일요일까지)\nCU는 안 함. 거지는 GS 감.",
    "source": "cvs",
    "store": "gs25",
    "category": "음료",
    "priority": 1
  }
]
```

---

## 5. 프론트엔드 설계

### 5.1 화면 구조

```
┌─────────────────────────────────┐
│  거지세끼 🍚                  ⚙️ │  ← 상단 헤더
├─────────────────────────────────┤
│  [오늘] [편의점] [올영] [다이소] [핫딜] │  ← 탭 네비게이션
├─────────────────────────────────┤
│                                 │
│  ┌─────────────────────────┐   │
│  │ 🔥 핫식스 1+1 떴다       │   │  ← 피드 카드
│  │ GS25 ㄱㄱ (일요일까지)    │   │
│  │ CU는 안 함. 거지는 GS 감. │   │
│  │              [GS25] 3/16까지│   │
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │ 💰 올영 메디힐 10+1       │   │
│  │ 개당 545원. 사재기 각.    │   │
│  │              [올영] 세일중 │   │
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │ 🏷️ 쿠팡 에어팟 역대 최저가 │   │
│  │ 218,000원. 뽐뿌 추천 42   │   │
│  │              [핫딜] 오늘   │   │
│  └─────────────────────────┘   │
│                                 │
│  ... (스크롤)                   │
│                                 │
├─────────────────────────────────┤
│  [🏠홈] [🏪편의점] [💄올영] [🛒다이소] [🔥핫딜]│  ← 하단 탭바
└─────────────────────────────────┘
```

### 5.2 탭별 상세

**[오늘] 탭 (메인)**
- 데일리 AI 큐레이션 피드
- 카드 리스트 형태, 세로 스크롤
- 각 카드에 소스 태그 (편의점/올영/다이소/핫딜)
- Pull-to-refresh로 최신 피드 불러오기

**[편의점] 탭**
- 편의점 4사 탭 (GS25/CU/세븐/이마트24/전체)
- 행사 타입 필터 (1+1/2+1/할인/전체)
- 카테고리 필터 (음료/과자/간편식사/생활용품)
- 상품 카드: 상품명 + 가격 + 행사타입 뱃지 + 이미지
- "이 상품 다른 편의점에서는?" 비교 기능

**[올영] 탭**
- 현재 세일 상품 리스트
- 카테고리 필터 (스킨케어/메이크업/헤어/바디/건강)
- 할인율 높은 순 정렬
- 올영세일/올영데이 일정 캘린더
- 1+1, 올영픽 특가 뱃지

**[다이소] 탭**
- 이번 달 신상 리스트
- 베스트셀러 랭킹
- 카테고리 필터
- AI 가성비 추천 점수 표시
- 가격대 필터 (1000원/2000원/3000원/5000원)

**[핫딜] 탭**
- 뽐뿌 핫딜 실시간 TOP
- 추천수 기반 정렬
- 카테고리 태그
- 원본 링크 바로가기
- AI 한줄 요약

### 5.3 디자인 톤

- **컬러**: 배경 흰색/연한 그레이, 포인트 컬러 **초록색 계열** (돈/절약 이미지)
- **폰트**: Pretendard (한국어 웹폰트)
- **카드 스타일**: 둥근 모서리, 그림자 살짝, 여백 넉넉
- **카피 톤**: 구어체 반말, 이모지 적절히, "거지력" 느껴지는 실용적 문장
- **B안 (깔끔 피드 + 유머 카피) 기반**: UI는 모던 미니멀, 텍스트가 웃긴 구조
- **PWA 지원**: 홈 화면 추가 가능하도록 manifest.json 설정

---

## 6. 프로젝트 디렉토리 구조

```
~/geoji-sekki/
├── backend/
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── config.py                  # 환경변수, 설정
│   ├── database.py                # SQLite + SQLAlchemy 설정
│   ├── models.py                  # DB 모델 정의
│   ├── schemas.py                 # Pydantic 스키마
│   ├── crawlers/
│   │   ├── __init__.py
│   │   ├── base.py                # 크롤러 베이스 클래스
│   │   ├── pyony_crawler.py       # 편의점 (pyony.com)
│   │   ├── ppomppu_crawler.py     # 뽐뿌 핫딜
│   │   ├── oliveyoung_crawler.py  # 올리브영
│   │   └── daiso_crawler.py       # 다이소
│   ├── services/
│   │   ├── __init__.py
│   │   ├── feed_service.py        # 데일리 피드 생성 (AI 큐레이션)
│   │   ├── compare_service.py     # 편의점 간 비교
│   │   └── llm_service.py         # DeepSeek API 래퍼
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── feed.py                # /api/feed
│   │   ├── cvs.py                 # /api/cvs
│   │   ├── oliveyoung.py          # /api/oliveyoung
│   │   ├── daiso.py               # /api/daiso
│   │   └── hotdeals.py            # /api/hotdeals
│   ├── scheduler.py               # APScheduler 크롤링 스케줄
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── FeedCard.jsx       # 피드 카드 컴포넌트
│   │   │   ├── TabBar.jsx         # 하단 탭바
│   │   │   ├── FilterBar.jsx      # 필터 (카테고리, 행사타입)
│   │   │   ├── StoreTag.jsx       # 소스 태그 뱃지
│   │   │   └── ProductCard.jsx    # 상품 카드 컴포넌트
│   │   ├── pages/
│   │   │   ├── TodayFeed.jsx      # [오늘] 탭
│   │   │   ├── CvsPage.jsx        # [편의점] 탭
│   │   │   ├── OliveyoungPage.jsx # [올영] 탭
│   │   │   ├── DaisoPage.jsx      # [다이소] 탭
│   │   │   └── HotdealsPage.jsx   # [핫딜] 탭
│   │   ├── hooks/
│   │   │   ├── useApi.js          # React Query 훅
│   │   │   └── useFilters.js      # 필터 상태 훅
│   │   ├── stores/
│   │   │   └── appStore.js        # Zustand 스토어
│   │   └── styles/
│   │       └── index.css          # Tailwind 진입점
│   ├── public/
│   │   ├── manifest.json          # PWA 매니페스트
│   │   └── favicon.ico
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── data/
│   └── geojisekki.db             # SQLite DB 파일
├── logs/
│   └── crawler.log
├── .env
├── .env.example
├── docker-compose.yml             # (선택) 컨테이너화
└── README.md
```

---

## 7. Phase별 개발 계획

### Phase 0 — 환경 세팅 (반나절)
**상태**: ⬜ 미시작

- [ ] 프로젝트 루트 생성
  ```bash
  mkdir -p ~/geoji-sekki/{backend/{crawlers,services,routers},frontend,data,logs}
  ```
- [ ] Python 가상환경 + 패키지 설치
  ```bash
  cd ~/geoji-sekki/backend
  python3 -m venv .venv && source .venv/bin/activate
  pip install fastapi uvicorn httpx beautifulsoup4 sqlalchemy \
              aiofiles python-dotenv openai apscheduler lxml
  ```
- [ ] `.env` 파일 생성
  ```env
  DEEPSEEK_API_KEY=sk-xxxx
  DEEPSEEK_BASE_URL=https://api.deepseek.com
  DEEPSEEK_MODEL=deepseek-chat
  APP_PORT=8100
  DB_PATH=/Users/zzimong/geoji-sekki/data/geojisekki.db
  LOG_PATH=/Users/zzimong/geoji-sekki/logs/crawler.log
  TELEGRAM_BOT_TOKEN=xxxx
  TELEGRAM_CHAT_ID=xxxx
  ```
- [ ] DeepSeek API 연결 테스트
- [ ] SQLite DB 초기화 (테이블 생성)
- [ ] FastAPI 기본 서버 기동 확인 (`/api/health`)
- [ ] Frontend 초기화
  ```bash
  cd ~/geoji-sekki
  npm create vite@latest frontend -- --template react
  cd frontend
  npm install axios @tanstack/react-query zustand react-router-dom lucide-react
  npx tailwindcss init -p
  ```

### Phase 1 — 편의점 크롤러 + 기본 API (2~3일)
**상태**: ⬜ 미시작

- [ ] `pyony_crawler.py` 구현
  - [ ] pyony.com HTML 구조 분석
  - [ ] 편의점 4사 행사 상품 파싱 (상품명, 가격, 행사타입, 카테고리, 이미지)
  - [ ] 크롤링 결과 → SQLite 저장
  - [ ] 중복 체크 로직
  - [ ] 에러 핸들링 + 재시도 (3회)
- [ ] `cvs.py` 라우터 구현
  - [ ] `GET /api/cvs` (전체, 필터 지원)
  - [ ] `GET /api/cvs/compare` (편의점 간 비교)
- [ ] 크롤러 수동 실행 테스트
- [ ] 데이터 검증 (실제 pyony 데이터와 대조)

### Phase 2 — 뽐뿌 크롤러 (1~2일)
**상태**: ⬜ 미시작

- [ ] `ppomppu_crawler.py` 구현
  - [ ] 뽐뿌 핫딜 게시판 HTML 구조 분석
  - [ ] 제목, 가격, 추천수, 댓글수, 원본 링크 파싱
  - [ ] DeepSeek로 카테고리 자동 분류 + 한줄 요약
  - [ ] SQLite 저장
- [ ] `hotdeals.py` 라우터 구현
  - [ ] `GET /api/hotdeals` (추천순, 최신순)
- [ ] 크롤링 주기 설정 (1일 2회)

### Phase 3 — 올리브영 크롤러 (2~3일)
**상태**: ⬜ 미시작

- [ ] 올리브영 모바일 웹(m.oliveyoung.co.kr) 구조 분석
  - [ ] 세일 페이지 HTML/API 확인
  - [ ] JS 렌더링 필요 여부 확인 → Playwright 도입 판단
- [ ] `oliveyoung_crawler.py` 구현
  - [ ] 세일 상품 파싱 (상품명, 브랜드, 정가, 할인가, 할인율, 이벤트타입)
  - [ ] 1+1, 올영픽 구분
  - [ ] SQLite 저장
- [ ] `oliveyoung.py` 라우터 구현
- [ ] 올영세일/올영데이 일정 캘린더 데이터

### Phase 4 — 다이소 크롤러 (1~2일)
**상태**: ⬜ 미시작

- [ ] daisomall.co.kr 구조 분석
- [ ] `daiso_crawler.py` 구현
  - [ ] 신상품 목록 파싱
  - [ ] 베스트셀러 랭킹 파싱
  - [ ] DeepSeek로 가성비 추천 점수 + 코멘트 생성
  - [ ] SQLite 저장
- [ ] `daiso.py` 라우터 구현
- [ ] 크롤링 주기 설정 (월 2회)

### Phase 5 — AI 데일리 피드 생성 (2~3일)
**상태**: ⬜ 미시작

- [ ] `feed_service.py` 구현
  - [ ] 오늘 기준 활성 데이터 수집 로직
  - [ ] DeepSeek 큐레이션 프롬프트 작성 + 테스트
  - [ ] 거지세끼 톤 카피 생성 품질 튜닝
  - [ ] 피드 결과 → SQLite `feeds` 테이블 저장
- [ ] `feed.py` 라우터 구현
  - [ ] `GET /api/feed` (오늘)
  - [ ] `GET /api/feed?date=` (과거)
- [ ] 매일 07:00 KST 자동 생성 스케줄러
- [ ] 피드 품질 수동 검수 (3~5일치)

### Phase 6 — 프론트엔드 MVP (5~7일)
**상태**: ⬜ 미시작

- [ ] 레이아웃 + 라우팅 설정
- [ ] 하단 탭바 컴포넌트
- [ ] [오늘] 탭 — 데일리 피드 카드 리스트
- [ ] [편의점] 탭 — 편의점별 필터 + 행사 상품 리스트
- [ ] [올영] 탭 — 세일 상품 리스트 + 카테고리 필터
- [ ] [다이소] 탭 — 신상/베스트 리스트
- [ ] [핫딜] 탭 — 뽐뿌 핫딜 리스트
- [ ] PWA manifest.json + 서비스 워커
- [ ] 반응형 모바일 최적화
- [ ] API 연동 + React Query 캐싱
- [ ] Pull-to-refresh 구현
- [ ] 로딩/에러 상태 처리

### Phase 7 — 스케줄러 + 모니터링 (1~2일)
**상태**: ⬜ 미시작

- [ ] APScheduler 전체 크롤링 스케줄 등록
  ```
  편의점: 매주 월 06:00
  뽐뿌: 매일 08:00, 18:00
  올영: 주 2회 (월/목) 07:00
  다이소: 월 2회 (1일, 15일) 07:00
  피드 생성: 매일 07:30
  ```
- [ ] Telegram 알림 연동
  - [ ] 크롤러 실패 시 알림
  - [ ] 일일 크롤링 요약 리포트
- [ ] 로그 설정 (파일 로테이션)
- [ ] `/api/health` 크롤러별 상태 포함

### Phase 8 — 도메인 + 배포 (반나절)
**상태**: ⬜ 미시작

- [ ] Cloudflare Tunnel 설정 (geojisekki.zzimong.com)
- [ ] Frontend 빌드 → FastAPI static files 서빙
- [ ] systemd 서비스 등록 (맥미니 재시작 시 자동 시작)
  ```bash
  # macOS는 launchd 사용
  ~/Library/LaunchAgents/com.zzimong.geojisekki.plist
  ```
- [ ] SSL 확인 (Cloudflare 자동)
- [ ] 실사용 테스트 (모바일 브라우저)

### Phase 9 — OpenClaw 연동 (1~2일)
**상태**: ⬜ 미시작

- [ ] `skills/geojisekki/SKILL.md` 작성
- [ ] 쿠로미 크롤링 자동화 설정
  ```
  - 스케줄 기반 크롤러 실행
  - 실패 시 호타루에 디버깅 위임
  - 텔레그램 그룹 리포트
  ```
- [ ] 호타루 크롤러 유지보수 룰
  ```
  - 크롤링 실패 시 사이트 구조 변경 확인
  - 셀렉터 자동 수정 시도
  - 수정 불가 시 건호에게 에스컬레이션
  ```
- [ ] 텔레그램 명령어
  ```
  /거지 오늘        → 오늘의 피드 요약
  /거지 편의점      → 이번 주 편의점 TOP 5
  /거지 핫딜        → 지금 핫딜 TOP 3
  /거지 상태        → 크롤러 상태 확인
  ```

---

## 8. 향후 확장 계획 (MVP 이후)

### 2차 확장
- [ ] 개인화 알고리즘 (사용자 프로필 + 행동 기반 가중치)
- [ ] 정가거부 유튜브 자막 기반 정보 추출
- [ ] 푸시 알림 (PWA Web Push)
- [ ] 공유 기능 (카카오톡 공유하기)
- [ ] 커뮤니티 핫딜 소스 추가 (에펨코리아, 클리앙)

### 3차 확장
- [ ] 카드 혜택 비교 (카드고릴라 데이터 활용)
- [ ] 알뜰 요금제 비교
- [ ] 청년 정책/지원금 안내
- [ ] 사용자 리뷰/인증 커뮤니티 ("이거 진짜 가성비 좋음" 인증)
- [ ] 게이미피케이션 (거지 레벨, 절약왕 뱃지)
- [ ] 사업자등록 + 카드사 제휴 CPA 수익화

---

## 9. 리스크 & 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| 크롤링 소스 구조 변경 | 높음 | 높음 | OpenClaw 자동 감지 + 호타루 수정, pyony 대안 소스 확보 |
| 올리브영 JS 렌더링 이슈 | 중간 | 중간 | Playwright 도입, 모바일 웹/API 우회 |
| DeepSeek API 불안정 | 낮음 | 중간 | Gemini Flash 폴백, 로컬 Ollama 비상용 |
| 크롤링 법적 이슈 | 낮음 | 높음 | robots.txt 준수, 원본 링크 항상 제공, 과도한 트래픽 금지 |
| pyony.com 서비스 중단 | 낮음 | 높음 | 편의점 직접 크롤링 전환 (마트몬 등 대안) |
| 사용자 유입 부족 | 중간 | 중간 | SNS 바이럴 (거지방 커뮤니티), 카카오톡 공유 최적화 |

---

## 10. 일정 요약

| Phase | 내용 | 예상 기간 | 누적 |
|-------|------|-----------|------|
| 0 | 환경 세팅 | 0.5일 | 0.5일 |
| 1 | 편의점 크롤러 + API | 2~3일 | 3.5일 |
| 2 | 뽐뿌 크롤러 | 1~2일 | 5.5일 |
| 3 | 올영 크롤러 | 2~3일 | 8.5일 |
| 4 | 다이소 크롤러 | 1~2일 | 10.5일 |
| 5 | AI 데일리 피드 | 2~3일 | 13.5일 |
| 6 | 프론트엔드 MVP | 5~7일 | 20.5일 |
| 7 | 스케줄러 + 모니터링 | 1~2일 | 22.5일 |
| 8 | 도메인 + 배포 | 0.5일 | 23일 |
| 9 | OpenClaw 연동 | 1~2일 | 25일 |

**총 예상: 약 3~4주 (퇴근 후 작업 기준)**

---

## 부록 A. 거지세끼 카피 톤 가이드

### 원칙
1. **반말 구어체**: "~임", "~각", "~ㄱㄱ", "~인듯"
2. **핵심 숫자 먼저**: 가격, 할인율, 기한을 앞에 배치
3. **비교로 임팩트**: "CU에서 1,200원인 걸 GS에서 600원에"
4. **행동 유도**: "지금 사라", "이번 주까지", "재고 소진 중"
5. **이모지**: 카드당 1~2개, 과하지 않게

### 예시

**편의점**:
```
🔥 핫식스 1+1 떴다
GS25 ㄱㄱ (일요일까지). CU는 안 함. 거지는 GS 감.
```

**올리브영**:
```
💄 메디힐 10+1 사재기 각
개당 545원. 올영 세일 가격임. 평소 800원짜리.
```

**다이소**:
```
🏷️ 다이소 충전케이블 C타입 1m
2,000원. 올영에서 비슷한 거 8,000원 함. 거지력 발동.
```

**핫딜**:
```
🎧 에어팟 프로2 역대 최저가 근접
218,000원. 뽐뿌 추천 42. 지금 아니면 언제 삼.
```
