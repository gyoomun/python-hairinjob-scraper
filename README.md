# HairinJob 스크래퍼

hairinjob.com 채용 정보 자동 수집 도구

---

## 📋 프로젝트 개요

헤어샵 채용정보 플랫폼인 hairinjob.com에서 채용 공고를 자동으로 수집하고 구조화된 데이터로 저장하는 Python 기반 스크래퍼입니다.

### 주요 기능
- 🔐 Playwright를 이용한 세션 쿠키 자동 수집 (10개)
- 🚀 병렬 처리를 통한 고속 다중 페이지 스크래핑
- 💾 JSON 또는 PostgreSQL 데이터베이스 저장 지원
- 🔍 채용 공고 상세 정보 파싱
- 📊 타임스탬프 기반 증분 저장

---

## 🏗️ 프로젝트 구조

```
python-hairinjob/
├── main.py                    # 메인 스크래핑 로직
├── requirements.txt           # 의존성 패키지
├── schema.sql                 # PostgreSQL 스키마 정의
├── .env                       # DB 접속 정보 (git 제외)
├── .env.example               # 환경변수 샘플
├── cookies/                   # 세션 쿠키 저장소
│   └── cookies_[1-10].json
├── db/                        # PostgreSQL 연동 모듈
│   ├── __init__.py
│   ├── config.py             # DB 접속 설정
│   ├── database.py           # 연결 및 초기화
│   └── queries.py            # CRUD 쿼리 함수
├── storage/                   # 저장 전략 모듈
│   ├── __init__.py
│   ├── base.py               # 추상 인터페이스
│   ├── json_storage.py       # JSON 저장 구현
│   ├── db_storage.py         # DB 저장 구현
│   └── hybrid_storage.py     # JSON+DB 저장 구현
├── scraping-result/          # JSON 저장 결과물
│   └── [timestamp]/
│       ├── all_jobs.json     # 통합 데이터
│       └── cookies_[N]/      # 쿠키별 페이지 데이터
└── viewer/                    # HTML 뷰어 생성 도구
```

---

## 🚀 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 실행 방법

#### 쿠키 수집
```bash
python main.py --mode collect-cookies
```

#### 전체 페이지 스크래핑 (JSON 저장)
```bash
python main.py --mode scrape-all --storage json
```

#### 전체 페이지 스크래핑 (DB 저장)
```bash
python main.py --mode scrape-all --storage db
```

#### 전체 페이지 스크래핑 (JSON + DB)
```bash
python main.py --mode scrape-all --storage both
```

---

## 📊 데이터베이스 저장 체제 구현 가이드

### Phase 1: 환경 설정

#### ✅ 1. PostgreSQL 설치 및 데이터베이스 생성

**Ubuntu/WSL:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start

# 데이터베이스 생성
sudo -u postgres psql
CREATE DATABASE hairinjob;
CREATE USER hairinjob_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE hairinjob TO hairinjob_user;
\q
```

**Docker 사용 (권장):**
```bash
docker run -d \
  --name hairinjob-postgres \
  -e POSTGRES_DB=hairinjob \
  -e POSTGRES_USER=hairinjob_user \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  postgres:15-alpine
```

---

#### ✅ 2. requirements.txt에 psycopg2-binary 추가

```txt
requests==2.31.0
playwright==1.40.0
beautifulsoup4==4.12.3
lxml==5.1.0
psycopg2-binary==2.9.9     # PostgreSQL 드라이버
python-dotenv==1.0.0       # 환경변수 로드
```

**설치:**
```bash
pip install -r requirements.txt
```

---

#### ✅ 3. .env 파일 생성

**.env** (실제 접속 정보, git 제외):
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hairinjob
DB_USER=hairinjob_user
DB_PASSWORD=your_password_here
```

**.env.example** (샘플, git 포함):
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hairinjob
DB_USER=hairinjob_user
DB_PASSWORD=change_me
```

**.gitignore에 추가:**
```
.env
```

---

#### ✅ 4. schema.sql 파일 생성

```sql
-- 채용공고 메인 테이블
CREATE TABLE job_postings (
    idx VARCHAR(20) PRIMARY KEY,
    company_name VARCHAR(200),
    title TEXT,
    detail_url VARCHAR(500),
    positions TEXT,
    location VARCHAR(100),
    salary VARCHAR(100),
    gender VARCHAR(20),
    deadline VARCHAR(50),
    grade VARCHAR(20),
    priority_badge VARCHAR(20),
    special_badges JSONB,
    phone VARCHAR(20),

    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    page_number INTEGER,
    cookie_set INTEGER
);

-- 스크래핑 세션 이력
CREATE TABLE scrape_sessions (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_pages INTEGER,
    total_jobs INTEGER,
    new_jobs INTEGER,
    updated_jobs INTEGER,
    num_cookies INTEGER,
    status VARCHAR(20),
    error_message TEXT
);

-- 인덱스
CREATE INDEX idx_company_name ON job_postings(company_name);
CREATE INDEX idx_location ON job_postings(location);
CREATE INDEX idx_scraped_at ON job_postings(scraped_at DESC);
CREATE INDEX idx_phone ON job_postings(phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_special_badges ON job_postings USING GIN(special_badges);

-- 자동 updated_at 트리거
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

#### ✅ 5. db/ 디렉토리 및 모듈 생성

```bash
mkdir -p db
touch db/__init__.py
touch db/config.py
touch db/database.py
touch db/queries.py
```

---

### Phase 2: DB 모듈 구현

#### ✅ 6. db/config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'hairinjob'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
}

def get_connection_string():
    """PostgreSQL 연결 문자열 생성"""
    return (
        f"host={DB_CONFIG['host']} "
        f"port={DB_CONFIG['port']} "
        f"dbname={DB_CONFIG['database']} "
        f"user={DB_CONFIG['user']} "
        f"password={DB_CONFIG['password']}"
    )
```

---

#### ✅ 7. db/database.py

```python
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from .config import get_connection_string

@contextmanager
def get_db_connection():
    """PostgreSQL 연결 컨텍스트 매니저"""
    conn = psycopg2.connect(
        get_connection_string(),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"DB 오류 발생, 롤백: {e}")
        raise
    finally:
        conn.close()

def init_database():
    """테이블 생성"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        with open('schema.sql', 'r', encoding='utf-8') as f:
            cursor.execute(f.read())
        print("✓ 데이터베이스 초기화 완료")

def test_connection():
    """DB 연결 테스트"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✓ PostgreSQL 연결 성공")
            return True
    except Exception as e:
        print(f"✗ PostgreSQL 연결 실패: {e}")
        return False
```

---

#### ✅ 8. db/queries.py

```python
import json
from psycopg2.extras import execute_values

def batch_insert_jobs(conn, jobs_list, page_num, cookie_idx):
    """대량 저장 (UPSERT)"""
    cursor = conn.cursor()

    values = []
    for job in jobs_list:
        special_badges_json = json.dumps(job.get('special_badges', []))
        values.append((
            job.get('idx'),
            job.get('company_name'),
            job.get('title'),
            job.get('detail_url'),
            job.get('positions'),
            job.get('location'),
            job.get('salary'),
            job.get('gender'),
            job.get('deadline'),
            job.get('grade'),
            job.get('priority_badge'),
            special_badges_json,
            job.get('phone'),
            page_num,
            cookie_idx
        ))

    execute_values(cursor, '''
        INSERT INTO job_postings
        (idx, company_name, title, detail_url, positions,
         location, salary, gender, deadline, grade,
         priority_badge, special_badges, phone,
         page_number, cookie_set)
        VALUES %s
        ON CONFLICT (idx) DO UPDATE SET
            updated_at = NOW(),
            phone = COALESCE(EXCLUDED.phone, job_postings.phone)
    ''', values)

def start_scrape_session(conn, total_pages, num_cookies):
    """스크래핑 세션 시작"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scrape_sessions (total_pages, num_cookies, status)
        VALUES (%s, %s, 'running')
        RETURNING id
    ''', (total_pages, num_cookies))
    return cursor.fetchone()['id']

def complete_scrape_session(conn, session_id, total_jobs, new_jobs, updated_jobs):
    """스크래핑 세션 완료"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE scrape_sessions
        SET completed_at = NOW(),
            total_jobs = %s,
            new_jobs = %s,
            updated_jobs = %s,
            status = 'completed'
        WHERE id = %s
    ''', (total_jobs, new_jobs, updated_jobs, session_id))
```

---

#### ✅ 9. DB 연결 테스트

**test_db.py 생성:**
```python
from db.database import test_connection, init_database

if __name__ == '__main__':
    print("PostgreSQL 연결 테스트 중...")
    if test_connection():
        print("\n데이터베이스 초기화 중...")
        init_database()
        print("\n✓ 모든 테스트 완료!")
    else:
        print("\n✗ DB 연결 실패")
```

**실행:**
```bash
python test_db.py
```

---

### Phase 3: Storage 추상화

#### ✅ 10. storage/ 디렉토리 생성

```bash
mkdir -p storage
touch storage/__init__.py
touch storage/base.py
touch storage/json_storage.py
touch storage/db_storage.py
touch storage/hybrid_storage.py
```

---

#### ✅ 11. storage/base.py (추상 인터페이스)

```python
from abc import ABC, abstractmethod

class StorageStrategy(ABC):
    """저장 전략 추상 클래스"""

    @abstractmethod
    def initialize(self):
        """초기화"""
        pass

    @abstractmethod
    def save_page(self, job_listings, page_num, cookie_idx, work_dir):
        """페이지 단위 저장"""
        pass

    @abstractmethod
    def save_all(self, all_jobs, work_dir):
        """전체 통합 저장"""
        pass
```

---

#### ✅ 12. storage/json_storage.py

```python
import json
import os
from .base import StorageStrategy

class JsonStorage(StorageStrategy):
    """기존 JSON 파일 저장 방식"""

    def initialize(self):
        pass

    def save_page(self, job_listings, page_num, cookie_idx, work_dir):
        """페이지별 JSON 파일 저장"""
        cookie_work_dir = os.path.join(work_dir, f"cookies_{cookie_idx}")
        os.makedirs(cookie_work_dir, exist_ok=True)

        page_file = os.path.join(cookie_work_dir, f"page_{page_num:03d}.json")
        with open(page_file, 'w', encoding='utf-8') as f:
            json.dump(job_listings, f, indent=2, ensure_ascii=False)

        print(f"  [{cookie_idx}] ✓ JSON 저장: {page_file}")

    def save_all(self, all_jobs, work_dir):
        """전체 통합 JSON 파일 저장"""
        all_jobs_file = os.path.join(work_dir, "all_jobs.json")
        with open(all_jobs_file, 'w', encoding='utf-8') as f:
            json.dump(all_jobs, f, indent=2, ensure_ascii=False)

        print(f"✓ 통합 JSON 저장: {all_jobs_file}")
```

---

#### ✅ 13. storage/db_storage.py

```python
from .base import StorageStrategy
from db.database import get_db_connection, test_connection
from db.queries import batch_insert_jobs, start_scrape_session, complete_scrape_session

class DbStorage(StorageStrategy):
    """PostgreSQL 데이터베이스 저장 방식"""

    def __init__(self):
        self.session_id = None

    def initialize(self):
        """DB 연결 테스트 및 세션 시작"""
        if not test_connection():
            raise Exception("PostgreSQL 연결 실패")

        with get_db_connection() as conn:
            self.session_id = start_scrape_session(conn, 0, 0)

        print(f"✓ DB 세션 시작 (ID: {self.session_id})")

    def save_page(self, job_listings, page_num, cookie_idx, work_dir):
        """페이지 데이터를 DB에 저장"""
        with get_db_connection() as conn:
            batch_insert_jobs(conn, job_listings, page_num, cookie_idx)

        print(f"  [{cookie_idx}] ✓ DB 저장: {len(job_listings)}개 항목")

    def save_all(self, all_jobs, work_dir):
        """세션 완료 기록"""
        with get_db_connection() as conn:
            complete_scrape_session(conn, self.session_id, len(all_jobs), 0, 0)

        print(f"✓ DB 세션 완료: 총 {len(all_jobs)}개 항목")
```

---

#### ✅ 14. storage/hybrid_storage.py

```python
from .base import StorageStrategy
from .json_storage import JsonStorage
from .db_storage import DbStorage

class HybridStorage(StorageStrategy):
    """JSON + DB 동시 저장"""

    def __init__(self):
        self.json_storage = JsonStorage()
        self.db_storage = DbStorage()

    def initialize(self):
        self.json_storage.initialize()
        self.db_storage.initialize()

    def save_page(self, job_listings, page_num, cookie_idx, work_dir):
        self.json_storage.save_page(job_listings, page_num, cookie_idx, work_dir)
        self.db_storage.save_page(job_listings, page_num, cookie_idx, work_dir)

    def save_all(self, all_jobs, work_dir):
        self.json_storage.save_all(all_jobs, work_dir)
        self.db_storage.save_all(all_jobs, work_dir)
```

---

#### ✅ 15. storage/__init__.py (팩토리 함수)

```python
from .json_storage import JsonStorage
from .db_storage import DbStorage
from .hybrid_storage import HybridStorage

def get_storage(storage_type):
    """저장 전략 팩토리"""
    if storage_type == 'json':
        return JsonStorage()
    elif storage_type == 'db':
        return DbStorage()
    elif storage_type == 'both':
        return HybridStorage()
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
```

---

### Phase 4: main.py 통합

#### ✅ 16. fetch_multiple_pages 함수 수정

```python
def fetch_multiple_pages(storage_type='json'):
    """옵션 3: 저장된 쿠키를 사용하여 여러 페이지를 스크래핑합니다."""
    from storage import get_storage

    # 저장 전략 선택
    storage = get_storage(storage_type)
    storage.initialize()

    # ... (기존 스크래핑 로직) ...

    # 저장 로직을 Strategy로 위임
    storage.save_page(job_listings, page_num, cookie_idx, work_dir)

    # 마지막에 전체 저장
    storage.save_all(all_jobs, work_dir)
```

---

#### ✅ 17. scrape_with_cookie 함수 수정

```python
def scrape_with_cookie(cookie_idx, cookie_file, start_page, end_page,
                       work_dir, num_cookies, storage):
    """특정 쿠키로 할당된 페이지 범위를 스크래핑합니다."""
    # ... (기존 로직) ...

    # 저장 로직 변경
    storage.save_page(job_listings, page_num, cookie_idx, work_dir)
```

---

### Phase 5: 테스트

#### ✅ 18. JSON 저장 테스트
```bash
python main.py --mode scrape-all --storage json
```

#### ✅ 19. DB 저장 테스트
```bash
python main.py --mode scrape-all --storage db
```

#### ✅ 20. 하이브리드 저장 테스트
```bash
python main.py --mode scrape-all --storage both
```

---

## 📊 체크리스트 요약

- **Phase 1** (환경 설정): 5단계
  - PostgreSQL 설치
  - 패키지 추가
  - 환경변수 설정
  - 스키마 정의
  - 모듈 구조 생성

- **Phase 2** (DB 모듈): 3단계
  - config.py
  - database.py
  - queries.py

- **Phase 3** (Storage 추상화): 5단계
  - base.py (인터페이스)
  - json_storage.py
  - db_storage.py
  - hybrid_storage.py
  - 팩토리 함수

- **Phase 4** (통합): 2단계
  - fetch_multiple_pages 수정
  - scrape_with_cookie 수정

- **Phase 5** (테스트): 3단계
  - JSON 모드
  - DB 모드
  - Both 모드

---

## 💡 유용한 SQL 쿼리

```sql
-- 최근 수집된 공고 조회
SELECT * FROM job_postings
ORDER BY scraped_at DESC
LIMIT 100;

-- 지역별 공고 수
SELECT location, COUNT(*) as count
FROM job_postings
GROUP BY location
ORDER BY count DESC;

-- 핸드폰 번호 있는 공고만
SELECT company_name, title, phone
FROM job_postings
WHERE phone IS NOT NULL;

-- 특정 배지 있는 공고
SELECT * FROM job_postings
WHERE special_badges @> '["급구"]'::jsonb;

-- 스크래핑 세션 이력
SELECT * FROM scrape_sessions
ORDER BY started_at DESC;
```

---

## 🔧 문제 해결

### PostgreSQL 연결 오류
```bash
# 서비스 확인
sudo service postgresql status

# 서비스 재시작
sudo service postgresql restart

# 연결 테스트
psql -h localhost -U hairinjob_user -d hairinjob
```

### 의존성 설치 오류
```bash
# psycopg2 컴파일 오류 시
sudo apt-get install libpq-dev python3-dev

# 또는 바이너리 버전 사용
pip install psycopg2-binary
```

---

## 📝 라이선스

이 프로젝트는 개인 학습/연구 목적으로 작성되었습니다.
