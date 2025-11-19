# HairinJob 스크래퍼 마이그레이션 가이드

> 다른 언어로 프로젝트를 마이그레이션하기 위한 완전한 기술 문서
>
> 작성일: 2025-10-29
> 원본 언어: Python 3.x
> 데이터베이스: PostgreSQL 15

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [데이터베이스 설계](#3-데이터베이스-설계)
4. [핵심 기능 명세](#4-핵심-기능-명세)
5. [데이터 플로우](#5-데이터-플로우)
6. [알고리즘 상세](#6-알고리즘-상세)
7. [CLI 인터페이스](#7-cli-인터페이스)
8. [환경 설정](#8-환경-설정)
9. [에러 처리](#9-에러-처리)
10. [성능 최적화](#10-성능-최적화)

---

## 1. 프로젝트 개요

### 1.1 목적
HairinJob.com의 채용공고 데이터를 자동으로 수집하여 PostgreSQL 데이터베이스에 저장하는 스크래핑 시스템

### 1.2 주요 기능
- **쿠키 기반 인증**: Playwright를 이용한 브라우저 자동화로 로그인 세션 유지
- **병렬 페이지 스크래핑**: ThreadPoolExecutor로 최대 10개의 쿠키 세션 동시 처리
- **상세정보 추출**: 로그인 후 각 채용공고의 상세페이지에서 연락처 정보 추출
- **세션 추적**: 각 스크래핑 실행을 세션으로 관리하여 데이터 추적 가능
- **유연한 저장**: JSON, DB, 또는 두 가지 모두에 저장 가능 (Strategy Pattern)

### 1.3 기술 스택

| 구분 | 기술 | 용도 |
|------|------|------|
| 브라우저 자동화 | Playwright | 로그인, 쿠키 수집 |
| HTTP 클라이언트 | requests | 페이지 스크래핑 |
| HTML 파싱 | BeautifulSoup4 (lxml) | DOM 파싱 및 데이터 추출 |
| 데이터베이스 | PostgreSQL 15 | 데이터 저장 |
| DB 드라이버 | psycopg2-binary | PostgreSQL 연결 |
| 병렬 처리 | concurrent.futures | ThreadPoolExecutor |
| 비동기 처리 | asyncio | Playwright async API |

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                     CLI Interface                       │
│  (main.py - argparse)                                  │
└────────────┬────────────────────────────────────────────┘
             │
             ├─── Mode 1: collect-cookies
             │    └─> Playwright Browser → cookies.json
             │
             ├─── Mode 2: test-page
             │    └─> Single Page Test
             │
             ├─── Mode 3: scrape-all
             │    ├─> Phase 1: Page Scraping
             │    │   └─> ThreadPoolExecutor (10 workers)
             │    │       └─> requests + cookies
             │    │           └─> BeautifulSoup parsing
             │    │               └─> Storage (json/db/both)
             │    │
             │    └─> Phase 2: Detail Scraping (if not --skip-pages)
             │        └─> Playwright Login (persistent context)
             │            └─> Extract cookies
             │            └─> requests loop (with cookie refresh every 20min)
             │                └─> Extract header info + phone numbers
             │                    └─> Update DB
             │
             └─── Mode 4: test-detail
                  └─> Single Detail Page Test

┌─────────────────────────────────────────────────────────┐
│                   Storage Layer                         │
│  (Strategy Pattern)                                     │
├─────────────────────────────────────────────────────────┤
│  BaseStorage (Abstract)                                 │
│  ├─> JsonStorage                                        │
│  ├─> DbStorage                                          │
│  └─> CompositeStorage (json + db)                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Database Layer                             │
├─────────────────────────────────────────────────────────┤
│  db/config.py     - Connection string                   │
│  db/database.py   - Connection context manager          │
│  db/queries.py    - All SQL queries                     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 디렉터리 구조

```
python-hairinjob/
├── main.py                    # 메인 엔트리포인트
├── requirements.txt           # Python 의존성
├── .env                       # 환경변수 (DB 설정)
├── .env.example
├── schema.sql                 # DB 스키마
├── run.sh                     # venv 자동 활성화 래퍼
│
├── cookies/                   # 쿠키 저장 디렉터리
│   └── cookies.json          # Playwright 쿠키 (10개 세트)
│
├── browser-data/             # Playwright persistent context
│   └── .last_reset           # 마지막 리셋 시간
│
├── scraping-result/          # JSON 저장 디렉터리
│   └── YYYYMMDD-HHMMSS/
│       ├── all_jobs.json
│       └── page_*.json
│
├── db/                       # 데이터베이스 모듈
│   ├── __init__.py
│   ├── config.py            # DB 연결 설정
│   ├── database.py          # 연결 관리
│   └── queries.py           # SQL 쿼리 함수
│
├── storage/                  # Storage Strategy Pattern
│   ├── __init__.py
│   ├── base.py              # Abstract base class
│   ├── json_storage.py      # JSON 저장 구현
│   ├── db_storage.py        # DB 저장 구현
│   └── factory.py           # Factory 패턴
│
├── migrations/               # DB 마이그레이션
│   ├── run_migration.py     # 마이그레이션 실행 스크립트
│   ├── 001_add_session_id.sql
│   └── 002_add_company_recruiter_info.sql
│
└── viewer/                   # HTML 뷰어 생성
    ├── generate_viewer.py
    └── viewer.html
```

---

## 3. 데이터베이스 설계

### 3.1 ERD

```
┌──────────────────────────────────────────────────────────┐
│                    scrape_sessions                       │
├──────────────────────────────────────────────────────────┤
│ PK  id              SERIAL                               │
│     started_at      TIMESTAMP                            │
│     completed_at    TIMESTAMP                            │
│     total_pages     INTEGER                              │
│     total_jobs      INTEGER                              │
│     new_jobs        INTEGER                              │
│     updated_jobs    INTEGER                              │
│     num_cookies     INTEGER                              │
│     status          VARCHAR(20)                          │
│     error_message   TEXT                                 │
└──────────────────────────────────────────────────────────┘
                          │
                          │ 1:N
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│                    job_postings                          │
├──────────────────────────────────────────────────────────┤
│ PK  idx                 VARCHAR(20)                      │
│     company_name        VARCHAR(200)                     │
│     title               TEXT                             │
│     detail_url          VARCHAR(500)                     │
│     positions           TEXT                             │
│     location            VARCHAR(100)                     │
│     salary              VARCHAR(100)                     │
│     gender              VARCHAR(20)                      │
│     deadline            VARCHAR(50)                      │
│     grade               VARCHAR(20)                      │
│     priority_badge      VARCHAR(20)                      │
│     special_badges      JSONB                            │
│     phone               VARCHAR(20)   -- 상세요강 전화번호 │
│     company_address     TEXT          -- 헤더: 업체주소   │
│     company_phone       VARCHAR(20)   -- 헤더: 전화번호   │
│     recruiter_name      VARCHAR(100)  -- 헤더: 담당자     │
│     recruiter_contact   VARCHAR(20)   -- 헤더: 담당자연락처│
│     scraped_at          TIMESTAMP                        │
│     updated_at          TIMESTAMP                        │
│     page_number         INTEGER                          │
│     cookie_set          INTEGER                          │
│ FK  session_id          INTEGER → scrape_sessions(id)    │
└──────────────────────────────────────────────────────────┘
```

### 3.2 인덱스 전략

```sql
-- 검색 최적화
CREATE INDEX idx_company_name ON job_postings(company_name);
CREATE INDEX idx_location ON job_postings(location);

-- 시간순 조회 최적화
CREATE INDEX idx_scraped_at ON job_postings(scraped_at DESC);
CREATE INDEX idx_updated_at ON job_postings(updated_at DESC);

-- 연락처 검색 (NULL 제외)
CREATE INDEX idx_phone ON job_postings(phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_company_phone ON job_postings(company_phone);
CREATE INDEX idx_recruiter_contact ON job_postings(recruiter_contact);

-- JSONB 배열 검색 (GIN 인덱스)
CREATE INDEX idx_special_badges ON job_postings USING GIN(special_badges);

-- 세션별 조회 최적화
CREATE INDEX idx_session_id ON job_postings(session_id);
```

### 3.3 UPSERT 로직

```sql
INSERT INTO job_postings (idx, company_name, title, ...)
VALUES (?, ?, ?, ...)
ON CONFLICT (idx) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    title = EXCLUDED.title,
    -- 기존 값이 있으면 유지, 새 값이 있으면 업데이트
    phone = COALESCE(EXCLUDED.phone, job_postings.phone),
    company_address = COALESCE(EXCLUDED.company_address, job_postings.company_address),
    -- ... (모든 필드 동일 패턴)
    updated_at = NOW();
```

### 3.4 자동 updated_at 트리거

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## 4. 핵심 기능 명세

### 4.1 쿠키 수집 (collect-cookies)

**목적**: Playwright를 사용하여 로그인된 세션의 쿠키를 수집

**알고리즘**:
```
1. Playwright Chromium 브라우저 실행 (headless=False)
2. 사용자가 수동으로 로그인 (60초 대기)
3. 쿠키 추출 (context.cookies())
4. 10개 세트의 독립적인 쿠키 생성:
   - 원본 쿠키를 복사
   - sameSite 속성 제거 (호환성)
   - 각 세트를 cookies/cookie_0.json ~ cookie_9.json으로 저장
5. cookies.json에 모든 쿠키 배열로 저장
```

**중요 사항**:
- `sameSite` 속성은 requests 호환을 위해 제거 필요
- 10개 세트는 병렬 처리 시 동시 요청을 위함

### 4.2 페이지 스크래핑 (scrape-all)

#### 4.2.1 병렬 처리 구조

```python
# ThreadPoolExecutor로 10개 워커 생성
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    for page_num in range(1, total_pages + 1):
        cookie_idx = (page_num - 1) % 10  # 라운드로빈
        cookie_file = f"cookies/cookie_{cookie_idx}.json"

        future = executor.submit(
            scrape_page,
            page_num,
            cookie_file,
            cookie_idx,
            storage
        )
        futures.append(future)

    # 모든 작업 완료 대기
    for future in as_completed(futures):
        result = future.result()
```

**병렬 처리 포인트**:
- 쿠키 세트 10개를 라운드로빈 방식으로 분배
- `page_num % 10`으로 쿠키 인덱스 결정
- `as_completed()`로 완료된 작업부터 결과 처리

#### 4.2.2 단일 페이지 스크래핑 로직

```python
def scrape_page(page_num, cookie_file, cookie_idx, storage):
    # 1. 쿠키 로드
    with open(cookie_file, 'r') as f:
        cookies = json.load(f)
    cookie_dict = {c['name']: c['value'] for c in cookies}

    # 2. 페이지 요청
    url = f"{TARGET_URL}?page={page_num}"
    response = requests.get(url, cookies=cookie_dict, headers=HEADERS)
    response.encoding = 'euc-kr'  # 중요: 인코딩 설정

    # 3. HTML 파싱 (최적화: SoupStrainer 사용)
    only_job_rows = SoupStrainer('tr', onclick=True)
    soup = BeautifulSoup(response.text, 'lxml', parse_only=only_job_rows)

    # 4. 각 채용공고 파싱
    jobs_list = []
    for row in soup.find_all('tr', onclick=True):
        job_data = extract_job_data(row)  # 상세 로직은 4.2.3 참조
        if job_data:
            jobs_list.append(job_data)

    # 5. Storage에 저장 (Strategy Pattern)
    storage.save_jobs(jobs_list, page_num, cookie_idx)

    return len(jobs_list)
```

**성능 최적화**:
- `SoupStrainer`: DOM 전체가 아닌 필요한 부분만 파싱 (메모리 절약)
- `lxml` 파서: 가장 빠른 파서 사용

#### 4.2.3 채용공고 데이터 추출

**HTML 구조 분석**:
```html
<tr onclick="..." style="cursor:pointer">
    <!-- idx 추출: onclick="location.href='/cms/s01_v.php?idx=100013'" -->

    <!-- 제목 & detail_url -->
    <a href="/cms/s01_v.php?idx=100013" style="...">제목</a>

    <!-- 모집 직종 -->
    <span class="span0301">디자이너,스탭</span>

    <!-- 지역 -->
    <span class="span0302">서울 강동구</span>

    <!-- 급여 -->
    <span class="span0303">면접 후 결정</span>

    <!-- 성별 -->
    <span class="span0304">무관</span>

    <!-- 마감일 -->
    <span class="span0305">상시채용</span>

    <!-- 학력 -->
    <span class="span0306">무관</span>

    <!-- 우선순위 뱃지 (선택) -->
    <img class="mList_new01" ...>  <!-- "오늘" -->
    <img class="mList_new02" ...>  <!-- "급구" -->

    <!-- 특수 뱃지 (선택, 다중 가능) -->
    <span class="special-badge">일급</span>
    <span class="special-badge">주급</span>
</tr>
```

**추출 코드**:
```python
def extract_job_data(row):
    job_data = {}

    # 1. idx 추출 (onclick 속성 파싱)
    onclick = row.get('onclick', '')
    # "location.href='/cms/s01_v.php?idx=100013'" 형태
    idx_match = re.search(r'idx=(\d+)', onclick)
    if idx_match:
        job_data['idx'] = idx_match.group(1)

    # 2. 회사명 (첫 번째 td의 텍스트)
    first_td = row.find('td')
    if first_td:
        job_data['company_name'] = first_td.get_text(strip=True)

    # 3. 제목 & detail_url (s01_v.php 링크)
    for link in row.find_all('a', href=True):
        if 's01_v.php' in link.get('href', ''):
            if link.get('style') and link.get_text(strip=True):
                job_data['title'] = link.get_text(strip=True)
                job_data['detail_url'] = link['href']  # 상대 경로
                break

    # 4. 모집 직종
    position_span = row.find('span', class_='span0301')
    if position_span:
        job_data['positions'] = position_span.get_text(strip=True)

    # 5. 지역
    location_span = row.find('span', class_='span0302')
    if location_span:
        job_data['location'] = location_span.get_text(strip=True)

    # 6. 급여
    salary_span = row.find('span', class_='span0303')
    if salary_span:
        job_data['salary'] = salary_span.get_text(strip=True)

    # 7. 성별
    gender_span = row.find('span', class_='span0304')
    if gender_span:
        job_data['gender'] = gender_span.get_text(strip=True)

    # 8. 마감일
    deadline_span = row.find('span', class_='span0305')
    if deadline_span:
        job_data['deadline'] = deadline_span.get_text(strip=True)

    # 9. 학력
    grade_span = row.find('span', class_='span0306')
    if grade_span:
        job_data['grade'] = grade_span.get_text(strip=True)

    # 10. 우선순위 뱃지
    if row.find('img', class_='mList_new01'):
        job_data['priority_badge'] = '오늘'
    elif row.find('img', class_='mList_new02'):
        job_data['priority_badge'] = '급구'

    # 11. 특수 뱃지 (다중)
    special_badges = []
    for badge in row.find_all('span', class_='special-badge'):
        badge_text = badge.get_text(strip=True)
        if badge_text:
            special_badges.append(badge_text)
    job_data['special_badges'] = special_badges

    return job_data if job_data.get('idx') else None
```

### 4.3 상세페이지 스크래핑

#### 4.3.1 Playwright 로그인 자동화

**영구 브라우저 컨텍스트 (Persistent Context)**:
```python
BROWSER_DATA_DIR = "browser-data"
TIMESTAMP_FILE = os.path.join(BROWSER_DATA_DIR, ".last_reset")
RESET_INTERVAL = 7 * 24 * 60 * 60  # 7일

# 1. 7일 경과 시 브라우저 데이터 리셋
if os.path.exists(TIMESTAMP_FILE):
    with open(TIMESTAMP_FILE, 'r') as f:
        last_reset = float(f.read().strip())
    if time.time() - last_reset > RESET_INTERVAL:
        shutil.rmtree(BROWSER_DATA_DIR)
        os.makedirs(BROWSER_DATA_DIR)

# 2. 영구 컨텍스트 실행 (쿠키, 로컬스토리지 유지)
context = await playwright.chromium.launch_persistent_context(
    BROWSER_DATA_DIR,
    headless=False,
    args=['--disable-blink-features=AutomationControlled']
)

# 3. 페이지 열기 및 새로고침
page = await context.new_page()
await page.goto(TARGET_URL, wait_until='networkidle')
await page.reload(wait_until='networkidle')

# 4. 안정화 대기
await asyncio.sleep(4)
```

**로그인 상태 확인**:
```python
page_content = await page.content()

# 페이지 소스에서 특정 URL 존재 여부로 판단
LOGOUT_URL = "https://www.hairinjob.com/member/login_ok.php?del=1"
is_logged_in = LOGOUT_URL in page_content

if not is_logged_in:
    # 로그인 필요
```

**자동 로그인**:
```python
LOGIN_URL = "https://www.hairinjob.com/cms/user/login.php"

await page.goto(LOGIN_URL, wait_until='networkidle')

# 아이디 입력 (첫 번째 input[name="userid"])
await page.locator('input[name="userid"]').first.fill('01028721278')

# 비밀번호 입력 (첫 번째 input[name="pwd"])
await page.locator('input[name="pwd"]').first.fill('235194')

# 3초 대기
await asyncio.sleep(3)

# 로그인 버튼 클릭 (첫 번째 button.btn_login)
await page.locator('button.btn_login').first.click()

# 마이페이지 도착 대기 (최대 30초)
await page.wait_for_url(
    'https://www.hairinjob.com/cms/p/mypage.php',
    timeout=30000
)
```

#### 4.3.2 쿠키 추출 및 갱신

**초기 쿠키 추출**:
```python
cookies = await context.cookies()
cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
last_cookie_refresh = time.time()
```

**20분마다 쿠키 갱신 (TODO: 구현 예정)**:
```python
COOKIE_REFRESH_INTERVAL = 20 * 60  # 1200초

for idx, job in enumerate(detail_jobs, 1):
    # 20분 경과 체크
    if time.time() - last_cookie_refresh > COOKIE_REFRESH_INTERVAL:
        print("🔄 쿠키 갱신 중... (20분 경과)")
        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        last_cookie_refresh = time.time()

    # requests 요청
    response = requests.get(detail_url, cookies=cookie_dict, ...)
```

#### 4.3.3 헤더 정보 추출

**HTML 구조**:
```html
<li class="left">업체주소</li>
<li class="right">서울 용산구 독서당로 70 현대리버티하우스 3층</li>

<li class="left">전화번호</li>
<li class="right">
    <span>02-797-1888</span>
    <div class="r_v_tel_layer01">로그인 안내...</div>
</li>

<li class="left">채용담당자</li>
<li class="right">
    <span>유영빈</span>
</li>

<li class="left">담당자연락처</li>
<li class="right">0508-4852-6192 <span>※ 안심번호 이용 중</span></li>
```

**추출 알고리즘 (중복 방지)**:
```python
# 초기화
company_address = None
company_phone = None
recruiter_name = None
recruiter_contact = None

found_fields = set()  # 이미 찾은 필드 추적

left_items = soup.find_all('li', class_='left')

for left_li in left_items:
    # 4개 모두 찾았으면 조기 종료
    if len(found_fields) >= 4:
        break

    label = left_li.get_text(strip=True)

    # 이미 찾은 필드는 스킵 (중복 방지)
    if label in found_fields:
        continue

    right_li = left_li.find_next_sibling('li', class_='right')
    if not right_li:
        continue

    if label == '업체주소':
        company_address = right_li.get_text(strip=True)
        found_fields.add('업체주소')

    elif label == '전화번호':
        span = right_li.find('span')
        if span:
            company_phone = span.get_text(strip=True)
            found_fields.add('전화번호')
        # span 없으면 found_fields에 추가 안함 → 다음 동일 라벨에서 재시도

    elif label == '채용담당자':
        span = right_li.find('span')
        if span:
            recruiter_name = span.get_text(strip=True)
            found_fields.add('채용담당자')

    elif label == '담당자연락처':
        text = right_li.get_text(strip=True)
        if text:
            # 숫자와 하이픈만 추출 (※ 등 특수문자 제거)
            first_token = text.split()[0] if text.split() else ''
            recruiter_contact = re.sub(r'[^0-9-]', '', first_token)
            if recruiter_contact:
                found_fields.add('담당자연락처')
```

**중요 포인트**:
1. **`found_fields` set**: 이미 찾은 라벨 추적하여 중복 방지
2. **조기 종료**: 4개 모두 찾으면 즉시 break (성능 최적화)
3. **재시도 가능**: 값 추출 실패 시 `found_fields`에 추가하지 않음
4. **담당자연락처 정제**: `re.sub(r'[^0-9-]', '', text)`로 숫자와 하이픈만 남김

#### 4.3.4 상세요강 전화번호 추출

**HTML 구조**:
```html
<div class="bottom_textbox">
    상세 내용 텍스트...
    연락처: 010-1234-5678
    ...
</div>
```

**추출 알고리즘**:
```python
# 1. "상세내용" 라벨을 가진 bottom_textbox 찾기
detail_content = None

for textbox in soup.find_all('div', class_='bottom_textbox'):
    prev_sibling = textbox.find_previous_sibling()
    if prev_sibling and '상세내용' in prev_sibling.get_text(strip=True):
        detail_content = textbox.get_text(strip=True)
        break

if detail_content:
    # 2. 핸드폰 번호 추출 (010만 허용)
    phone_pattern = r'010[-.\s]?\d{3,4}[-.\s]?\d{4}'
    phone_numbers = re.findall(phone_pattern, detail_content)

    if phone_numbers:
        # 3. 중복 제거 및 첫 번째 번호 사용
        unique_phones = list(set(phone_numbers))
        phone = unique_phones[0]
```

**정규식 설명**:
- `010`: 반드시 010으로 시작
- `[-.\s]?`: 하이픈, 점, 공백 중 0개 또는 1개
- `\d{3,4}`: 3~4자리 숫자
- `[-.\s]?`: 구분자
- `\d{4}`: 4자리 숫자

**매칭 예시**:
- `010-1234-5678` ✓
- `010.1234.5678` ✓
- `010 1234 5678` ✓
- `01012345678` ✓
- `010-123-5678` ✓
- `011-1234-5678` ✗ (010만 허용)

#### 4.3.5 DB 업데이트

```python
# UPSERT 패턴으로 업데이트
job_data = {
    'idx': job_idx,
    'company_name': company_name,
    'title': title,
    'detail_url': detail_url,
    'phone': phone,                         # 상세요강 전화번호
    'company_address': company_address,
    'company_phone': company_phone,
    'recruiter_name': recruiter_name,
    'recruiter_contact': recruiter_contact,
    'positions': '',  # 페이지 스크래핑에서 이미 저장됨
    'location': '',
    'salary': '',
    'gender': '',
    'deadline': '',
    'grade': '',
    'priority_badge': '',
    'special_badges': []
}

batch_insert_jobs(conn, [job_data], page_num=0, cookie_idx=0, session_id=session_id)
conn.commit()
```

**UPSERT 동작**:
- 기존 데이터의 다른 필드는 유지
- 새로 추출한 필드만 업데이트
- `COALESCE(EXCLUDED.*, job_postings.*)`로 NULL 체크

#### 4.3.6 랜덤 딜레이

```python
import random

# 각 요청 후 0.3~1.0초 랜덤 대기
delay = random.uniform(0.3, 1.0)
await asyncio.sleep(delay)
```

**목적**: 봇 탐지 회피 및 서버 부하 분산

---

## 5. 데이터 플로우

### 5.1 전체 플로우

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 쿠키 수집 (최초 1회)                                 │
│ python main.py --mode collect-cookies                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
            cookies/cookie_0.json ~ cookie_9.json 생성
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 페이지 스크래핑                                      │
│ python main.py --mode scrape-all --storage db               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ├─> Phase 1: 병렬 페이지 스크래핑
                          │   ├─> 쿠키 0 → Page 1, 11, 21, ...
                          │   ├─> 쿠키 1 → Page 2, 12, 22, ...
                          │   ├─> ...
                          │   └─> 쿠키 9 → Page 10, 20, 30, ...
                          │       └─> DB INSERT/UPDATE
                          │
                          └─> Phase 2: 상세페이지 스크래핑
                              ├─> Playwright 로그인
                              ├─> 쿠키 추출
                              ├─> DB에서 최근 세션의 detail_url 조회
                              │   (ORDER BY page_number ASC, idx ASC)
                              └─> 각 상세페이지 순회
                                  ├─> requests GET (쿠키 사용)
                                  ├─> 헤더 정보 추출
                                  ├─> 상세요강 전화번호 추출
                                  ├─> DB UPDATE
                                  └─> 랜덤 딜레이 (0.3~1.0초)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 결과 확인                                            │
│ - DB 쿼리로 확인                                             │
│ - 또는 JSON 뷰어 생성                                        │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 세션 추적 플로우

```
1. scrape_sessions INSERT
   ├─> id = 1 (auto increment)
   ├─> status = 'running'
   └─> started_at = NOW()

2. job_postings INSERT/UPDATE
   ├─> session_id = 1 (FK 참조)
   └─> 페이지별로 순차 저장

3. scrape_sessions UPDATE
   ├─> status = 'completed'
   ├─> completed_at = NOW()
   ├─> total_jobs = 1234
   ├─> new_jobs = 100
   └─> updated_jobs = 1134

4. 다음 실행 시 session_id = 2
   └─> 각 세션별 수집 데이터 추적 가능
```

### 5.3 Storage Strategy 플로우

```
create_storage(storage_type, result_dir)
    │
    ├─> 'json'
    │   └─> return JsonStorage(result_dir)
    │
    ├─> 'db'
    │   └─> return DbStorage()
    │
    └─> 'both'
        └─> return CompositeStorage([
                JsonStorage(result_dir),
                DbStorage()
            ])

storage.save_jobs(jobs_list, page_num, cookie_idx)
    │
    ├─> JsonStorage
    │   └─> JSON 파일에 저장
    │
    ├─> DbStorage
    │   └─> PostgreSQL에 UPSERT
    │
    └─> CompositeStorage
        └─> 두 storage 모두에 저장
```

---

## 6. 알고리즘 상세

### 6.1 쿠키 라운드로빈 분배

```python
# 페이지 번호 → 쿠키 인덱스 매핑
def get_cookie_index(page_num, total_cookies=10):
    return (page_num - 1) % total_cookies

# 예시
# Page 1 → Cookie 0
# Page 2 → Cookie 1
# ...
# Page 10 → Cookie 9
# Page 11 → Cookie 0 (순환)
# Page 12 → Cookie 1
```

### 6.2 중복 필드 방지 알고리즘

```python
found_fields = set()

for item in items:
    label = extract_label(item)

    # 이미 찾은 필드면 스킵
    if label in found_fields:
        continue

    value = extract_value(item)

    # 값 추출 성공 시에만 found_fields에 추가
    if value is not None:
        result[label] = value
        found_fields.add(label)
```

**핵심**:
- `found_fields`에 추가하는 시점 = 값 추출 성공 시
- 값 추출 실패 시 추가하지 않음 → 다음 동일 라벨에서 재시도

### 6.3 URL 정규화

```python
def normalize_detail_url(detail_url):
    """상대 경로를 절대 경로로 변환"""
    if detail_url and not detail_url.startswith('http'):
        return f"https://www.hairinjob.com{detail_url}"
    return detail_url

# /cms/s01_v.php?idx=12345
# → https://www.hairinjob.com/cms/s01_v.php?idx=12345
```

### 6.4 전화번호 정제

```python
def clean_phone_number(raw_text):
    """텍스트에서 숫자와 하이픈만 추출"""
    # "0508-4852-6192 ※ 안심번호 이용 중"
    # → "0508-4852-6192"

    first_token = raw_text.split()[0] if raw_text.split() else ''
    return re.sub(r'[^0-9-]', '', first_token)
```

### 6.5 세션별 최신 데이터 조회

```python
def get_latest_session_detail_urls(conn):
    # 1. 최근 세션 ID 조회
    latest_session_id = conn.execute(
        "SELECT MAX(id) FROM scrape_sessions"
    ).fetchone()[0]

    # 2. 해당 세션의 데이터만 조회
    return conn.execute(
        """
        SELECT idx, detail_url, company_name, title
        FROM job_postings
        WHERE session_id = ?
        ORDER BY page_number ASC, idx ASC
        """,
        (latest_session_id,)
    ).fetchall()
```

---

## 7. CLI 인터페이스

### 7.1 명령어 구조

```bash
python main.py --mode <MODE> [--storage <STORAGE>] [--skip-pages]
```

### 7.2 파라미터 상세

| 파라미터 | 필수 | 선택값 | 설명 |
|----------|------|--------|------|
| `--mode` | ✓ | `collect-cookies`, `test-page`, `scrape-all`, `test-detail` | 실행 모드 |
| `--storage` | △ | `json`, `db`, `both` | 저장 방식 (scrape-all 시 필수) |
| `--skip-pages` | ✗ | - | 페이지 스크래핑 건너뛰기 플래그 |

### 7.3 모드별 동작

#### Mode 1: collect-cookies
```bash
python main.py --mode collect-cookies
```

**동작**:
1. Playwright 브라우저 실행 (headless=False)
2. 60초 대기 (사용자 수동 로그인)
3. 쿠키 추출 및 저장 (10개 세트)

**출력 파일**:
- `cookies/cookie_0.json` ~ `cookie_9.json`
- `cookies/cookies.json` (전체 배열)

#### Mode 2: test-page
```bash
python main.py --mode test-page --storage json
```

**동작**:
1. 1페이지만 스크래핑 (테스트용)
2. 결과 출력 및 저장

#### Mode 3: scrape-all
```bash
# JSON만
python main.py --mode scrape-all --storage json

# DB만
python main.py --mode scrape-all --storage db

# 둘 다
python main.py --mode scrape-all --storage both

# 페이지 스크래핑 건너뛰고 상세페이지만
python main.py --mode scrape-all --storage db --skip-pages
```

**동작**:
1. **Phase 1: 페이지 스크래핑** (unless --skip-pages)
   - 병렬 처리 (10 workers)
   - Storage에 저장
2. **Phase 2: 상세페이지 스크래핑**
   - Playwright 로그인
   - 각 상세페이지 순회
   - 헤더 정보 + 전화번호 추출
   - DB 업데이트

#### Mode 4: test-detail
```bash
python main.py --mode test-detail
```

**동작**:
1. 하드코딩된 1개 URL 테스트
2. 상세정보 추출 및 출력

### 7.4 환경변수 (.env)

```bash
# PostgreSQL 설정
DB_HOST=localhost
DB_PORT=5433
DB_NAME=hairinjob
DB_USER=postgres
DB_PASSWORD=postgres
```

---

## 8. 환경 설정

### 8.1 Python 의존성 (requirements.txt)

```
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
playwright==1.40.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
```

### 8.2 Playwright 초기 설정

```bash
# 브라우저 설치
python -m playwright install chromium
```

### 8.3 PostgreSQL 설정

```sql
-- 데이터베이스 생성
CREATE DATABASE hairinjob;

-- 스키마 적용
\i schema.sql

-- 마이그레이션 적용 (필요 시)
python migrations/run_migration.py migrations/001_add_session_id.sql
python migrations/run_migration.py migrations/002_add_company_recruiter_info.sql
```

### 8.4 디렉터리 초기화

```bash
mkdir -p cookies
mkdir -p scraping-result
mkdir -p browser-data
```

---

## 9. 에러 처리

### 9.1 네트워크 에러

```python
try:
    response = requests.get(url, cookies=cookies, headers=headers, timeout=10)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"✗ 오류: {e}")
    continue  # 다음 작업 계속 진행
```

**전략**: 개별 페이지 실패는 로그만 남기고 전체 프로세스는 계속 진행

### 9.2 DB 연결 에러

```python
try:
    conn = psycopg2.connect(connection_string)
except psycopg2.Error as e:
    print(f"DB 연결 실패: {e}")
    sys.exit(1)  # 치명적 오류이므로 종료
```

### 9.3 Playwright 에러

```python
try:
    await page.goto(url, wait_until='networkidle', timeout=30000)
except PlaywrightTimeoutError:
    print("페이지 로드 타임아웃")
    # 재시도 또는 스킵
```

### 9.4 파싱 에러

```python
try:
    job_data = extract_job_data(row)
except Exception as e:
    print(f"파싱 오류 (row skipped): {e}")
    continue
```

**전략**: 개별 항목 파싱 실패는 무시하고 계속 진행

---

## 10. 성능 최적화

### 10.1 병렬 처리

```python
# ThreadPoolExecutor로 10개 워커
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(scrape_page, ...) for page in pages]
    for future in as_completed(futures):
        result = future.result()
```

**효과**: 단일 스레드 대비 약 8~10배 속도 향상

### 10.2 HTML 파싱 최적화

```python
# SoupStrainer로 필요한 부분만 파싱
only_job_rows = SoupStrainer('tr', onclick=True)
soup = BeautifulSoup(html, 'lxml', parse_only=only_job_rows)
```

**효과**: 메모리 사용량 50% 감소, 파싱 속도 30% 향상

### 10.3 인덱스 활용

```sql
-- 세션별 조회 최적화
CREATE INDEX idx_session_id ON job_postings(session_id);

-- 정렬 최적화
-- ORDER BY page_number ASC, idx ASC 쿼리에 유리하도록 복합 인덱스 고려
CREATE INDEX idx_page_idx ON job_postings(page_number, idx);
```

### 10.4 커넥션 풀링

**현재**: 각 저장마다 새 연결
**개선안**: 연결 풀 사용 (예: psycopg2.pool.SimpleConnectionPool)

### 10.5 배치 처리

```python
# 현재: 각 페이지마다 즉시 저장
# 개선안: 100개씩 모아서 배치 INSERT (선택 사항)
```

---

## 11. 추가 구현 필요 사항

### 11.1 쿠키 갱신 (TODO)

**현재 상태**: 계획만 수립됨
**구현 위치**: `main.py:720` (상세페이지 루프 내)

```python
last_cookie_refresh = time.time()
COOKIE_REFRESH_INTERVAL = 20 * 60

for idx, job in enumerate(detail_jobs, 1):
    if time.time() - last_cookie_refresh > COOKIE_REFRESH_INTERVAL:
        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        last_cookie_refresh = time.time()
```

### 11.2 에러 복구

**현재**: 에러 발생 시 해당 항목 스킵
**개선안**:
- 실패한 항목 별도 로그
- 재시도 메커니즘
- 실패한 항목만 재수집하는 모드

### 11.3 진행 상황 저장

**현재**: 중단 시 처음부터 재시작
**개선안**:
- 진행 상황을 DB 또는 파일에 저장
- 중단된 지점부터 재개 기능

### 11.4 로그 시스템

**현재**: print 문
**개선안**:
- Python logging 모듈 사용
- 로그 레벨 설정 (DEBUG, INFO, WARNING, ERROR)
- 파일 로그 저장

---

## 12. 마이그레이션 체크리스트

### 12.1 필수 구현 기능

- [ ] Playwright 브라우저 자동화
  - [ ] 영구 컨텍스트 (persistent context)
  - [ ] 쿠키 수집 및 저장
  - [ ] 로그인 자동화
- [ ] ThreadPoolExecutor 병렬 처리
- [ ] requests HTTP 클라이언트
- [ ] HTML 파싱 (BeautifulSoup 상당)
- [ ] PostgreSQL 연결 및 UPSERT
- [ ] 정규식 패턴 매칭
- [ ] JSON 직렬화/역직렬화
- [ ] 파일 시스템 작업
- [ ] CLI 인자 파싱
- [ ] 환경변수 로드

### 12.2 핵심 알고리즘

- [ ] 쿠키 라운드로빈 분배
- [ ] 중복 필드 방지 (found_fields set)
- [ ] URL 정규화
- [ ] 전화번호 정규식 추출 및 정제
- [ ] UPSERT 로직
- [ ] 세션 추적
- [ ] 랜덤 딜레이

### 12.3 데이터베이스

- [ ] 테이블 생성 (job_postings, scrape_sessions)
- [ ] 인덱스 생성
- [ ] 트리거 생성 (updated_at)
- [ ] 외래키 제약조건

### 12.4 성능 최적화

- [ ] SoupStrainer 상당 기능 (부분 파싱)
- [ ] lxml 파서 상당 (빠른 파서)
- [ ] 병렬 처리
- [ ] 커넥션 풀링 (선택)

### 12.5 에러 처리

- [ ] 네트워크 타임아웃
- [ ] DB 연결 실패
- [ ] 파싱 에러
- [ ] Playwright 타임아웃

---

## 13. 언어별 추천 라이브러리

### 13.1 Node.js

```javascript
// 브라우저 자동화
const playwright = require('playwright');

// HTTP 클라이언트
const axios = require('axios');

// HTML 파싱
const cheerio = require('cheerio');

// PostgreSQL
const { Pool } = require('pg');

// 환경변수
require('dotenv').config();

// CLI 파싱
const yargs = require('yargs');

// 병렬 처리
// Promise.all(), p-limit 라이브러리
```

### 13.2 Go

```go
// 브라우저 자동화
github.com/playwright-community/playwright-go

// HTTP 클라이언트
net/http (표준 라이브러리)

// HTML 파싱
github.com/PuerkitoBio/goquery

// PostgreSQL
github.com/lib/pq
github.com/jmoiron/sqlx

// 환경변수
github.com/joho/godotenv

// CLI 파싱
github.com/spf13/cobra

// 병렬 처리
goroutines + sync.WaitGroup
```

### 13.3 Java

```java
// 브라우저 자동화
com.microsoft.playwright:playwright

// HTTP 클라이언트
org.apache.httpcomponents:httpclient
okhttp3

// HTML 파싱
org.jsoup:jsoup

// PostgreSQL
org.postgresql:postgresql
com.zaxxer:HikariCP (Connection Pool)

// 환경변수
io.github.cdimascio:dotenv-java

// CLI 파싱
info.picocli:picocli

// 병렬 처리
ExecutorService, CompletableFuture
```

---

## 14. 주요 상수 및 설정값

```python
# URL
TARGET_URL = "https://www.hairinjob.com/cms/s01.php"
LOGIN_URL = "https://www.hairinjob.com/cms/user/login.php"
LOGOUT_URL = "https://www.hairinjob.com/member/login_ok.php?del=1"
MYPAGE_URL = "https://www.hairinjob.com/cms/p/mypage.php"

# 디렉터리
COOKIE_DIR = "cookies"
RESULT_DIR = "scraping-result"
BROWSER_DATA_DIR = "browser-data"

# 병렬 처리
MAX_WORKERS = 10
NUM_COOKIE_SETS = 10

# 타임아웃
PAGE_LOAD_TIMEOUT = 30000  # 30초 (밀리초)
REQUEST_TIMEOUT = 10  # 10초

# 딜레이
RANDOM_DELAY_MIN = 0.3  # 초
RANDOM_DELAY_MAX = 1.0  # 초

# 브라우저
BROWSER_RESET_INTERVAL = 7 * 24 * 60 * 60  # 7일

# 쿠키 갱신 (TODO)
COOKIE_REFRESH_INTERVAL = 20 * 60  # 20분

# 로그인 대기
LOGIN_WAIT_TIME = 60  # 60초 (쿠키 수집 모드)

# 인코딩
HTML_ENCODING = 'euc-kr'

# HTTP 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.hairinjob.com/cms/s01.php',
    'Upgrade-Insecure-Requests': '1'
}

# 로그인 자격 증명 (환경변수로 이동 권장)
LOGIN_USERID = '01028721278'
LOGIN_PASSWORD = '235194'

# 정규식 패턴
PHONE_PATTERN = r'010[-.\s]?\d{3,4}[-.\s]?\d{4}'
IDX_PATTERN = r'idx=(\d+)'
```

---

## 15. 중요 구현 노트

### 15.1 인코딩 주의사항
- 웹사이트는 `euc-kr` 인코딩 사용
- `response.encoding = 'euc-kr'` 필수 설정

### 15.2 쿠키 호환성
- Playwright 쿠키에 `sameSite` 속성 제거 필요
- requests에서 `sameSite` 미지원

### 15.3 영구 컨텍스트
- `launch_persistent_context()` 사용으로 로그인 세션 유지
- `browser-data/` 폴더에 브라우저 프로필 저장
- 7일마다 자동 리셋

### 15.4 중복 라벨 처리
- HTML에 같은 라벨이 여러 번 출현 가능
- `found_fields` set으로 첫 번째 값만 사용

### 15.5 UPSERT 전략
- `ON CONFLICT (idx) DO UPDATE`
- `COALESCE`로 NULL 값 처리
- 기존 데이터 보존하면서 새 데이터 추가

### 15.6 세션 추적
- 각 스크래핑 실행마다 고유 session_id
- 세션별 데이터 집계 가능
- 최근 세션의 데이터만 조회

### 15.7 URL 처리
- DB에는 상대 경로 저장 (`/cms/s01_v.php?idx=...`)
- 사용 시 절대 경로로 변환 필요

### 15.8 전화번호 정제
- 정규식: `r'[^0-9-]'`
- 숫자와 하이픈만 남김
- 특수문자 (※ 등) 제거

---

## 16. 테스트 시나리오

### 16.1 기본 플로우 테스트
```bash
# 1. 쿠키 수집
python main.py --mode collect-cookies

# 2. 1페이지 테스트
python main.py --mode test-page --storage json

# 3. 전체 스크래핑 (JSON)
python main.py --mode scrape-all --storage json

# 4. DB 확인
psql -U postgres -d hairinjob -c "SELECT COUNT(*) FROM job_postings;"

# 5. 상세페이지 스크래핑
python main.py --mode scrape-all --storage db --skip-pages
```

### 16.2 엣지 케이스 테스트
- 쿠키 파일 없음
- DB 연결 실패
- 빈 페이지
- 잘못된 HTML 구조
- 전화번호 없는 경우
- 헤더 정보 없는 경우

---

## 17. 참고 자료

### 17.1 외부 문서
- Playwright 공식 문서: https://playwright.dev/
- BeautifulSoup 문서: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- PostgreSQL 문서: https://www.postgresql.org/docs/

### 17.2 프로젝트 파일
- `schema.sql`: 데이터베이스 스키마
- `requirements.txt`: Python 의존성
- `migrations/`: DB 마이그레이션 히스토리
- `.env.example`: 환경변수 템플릿

---

## 부록 A: 전체 데이터 필드 매핑

| DB 컬럼 | 데이터 출처 | 추출 방법 | 비고 |
|---------|------------|----------|------|
| `idx` | 페이지 목록 | `onclick` 속성 정규식 | Primary Key |
| `company_name` | 페이지 목록 | 첫 번째 `<td>` 텍스트 | |
| `title` | 페이지 목록 | `s01_v.php` 링크 텍스트 | |
| `detail_url` | 페이지 목록 | `s01_v.php` 링크 href | 상대 경로 |
| `positions` | 페이지 목록 | `<span class="span0301">` | |
| `location` | 페이지 목록 | `<span class="span0302">` | |
| `salary` | 페이지 목록 | `<span class="span0303">` | |
| `gender` | 페이지 목록 | `<span class="span0304">` | |
| `deadline` | 페이지 목록 | `<span class="span0305">` | |
| `grade` | 페이지 목록 | `<span class="span0306">` | |
| `priority_badge` | 페이지 목록 | `<img class="mList_new0*">` | '오늘' 또는 '급구' |
| `special_badges` | 페이지 목록 | `<span class="special-badge">` | JSONB 배열 |
| `phone` | 상세페이지 | 상세요강 정규식 | 010 전화번호 |
| `company_address` | 상세페이지 | `<li class="left">업체주소` | 헤더 |
| `company_phone` | 상세페이지 | `<li class="left">전화번호` | 헤더, `<span>` |
| `recruiter_name` | 상세페이지 | `<li class="left">채용담당자` | 헤더, `<span>` |
| `recruiter_contact` | 상세페이지 | `<li class="left">담당자연락처` | 헤더, 정제 필요 |
| `page_number` | 시스템 | 스크래핑 시 전달 | 페이지 번호 |
| `cookie_set` | 시스템 | 라운드로빈 계산 | 0~9 |
| `session_id` | 시스템 | DB auto increment | FK |
| `scraped_at` | 시스템 | DB DEFAULT NOW() | |
| `updated_at` | 시스템 | DB TRIGGER | |

---

## 부록 B: SQL 쿼리 모음

### B.1 세션별 통계
```sql
SELECT
    s.id,
    s.started_at,
    s.completed_at,
    s.status,
    s.total_jobs,
    COUNT(j.idx) as actual_count
FROM scrape_sessions s
LEFT JOIN job_postings j ON j.session_id = s.id
GROUP BY s.id
ORDER BY s.started_at DESC;
```

### B.2 최근 수집 데이터
```sql
SELECT *
FROM job_postings
WHERE session_id = (SELECT MAX(id) FROM scrape_sessions)
ORDER BY page_number ASC, idx ASC
LIMIT 100;
```

### B.3 연락처 통계
```sql
SELECT
    COUNT(*) as total,
    COUNT(phone) as phone_count,
    COUNT(company_phone) as company_phone_count,
    COUNT(recruiter_contact) as recruiter_contact_count
FROM job_postings;
```

### B.4 지역별 집계
```sql
SELECT
    location,
    COUNT(*) as count
FROM job_postings
GROUP BY location
ORDER BY count DESC
LIMIT 20;
```

---

## 문서 끝

이 문서는 HairinJob 스크래퍼의 모든 기능을 다른 언어로 마이그레이션하기 위한 완전한 기술 명세입니다.

**작성자**: Claude Code
**최종 업데이트**: 2025-10-29
**버전**: 1.0
