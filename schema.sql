-- HairinJob 스크래퍼 데이터베이스 스키마
-- PostgreSQL 15

-- 채용공고 메인 테이블
CREATE TABLE IF NOT EXISTS job_postings (
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
    phone VARCHAR(20),                   -- 상세요강 본문에서 추출한 핸드폰번호

    -- 헤더 정보 (업체 및 담당자)
    company_address TEXT,                -- 업체주소
    company_phone VARCHAR(20),           -- 업체 대표 전화번호
    recruiter_name VARCHAR(100),         -- 채용담당자 이름
    recruiter_contact VARCHAR(20),       -- 채용담당자 연락처

    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    page_number INTEGER,
    cookie_set INTEGER,
    session_id INTEGER REFERENCES scrape_sessions(id)
);

-- 스크래핑 세션 이력
CREATE TABLE IF NOT EXISTS scrape_sessions (
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

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_company_name ON job_postings(company_name);
CREATE INDEX IF NOT EXISTS idx_location ON job_postings(location);
CREATE INDEX IF NOT EXISTS idx_scraped_at ON job_postings(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_updated_at ON job_postings(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_phone ON job_postings(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_special_badges ON job_postings USING GIN(special_badges);
CREATE INDEX IF NOT EXISTS idx_session_id ON job_postings(session_id);
CREATE INDEX IF NOT EXISTS idx_company_phone ON job_postings(company_phone);
CREATE INDEX IF NOT EXISTS idx_recruiter_contact ON job_postings(recruiter_contact);

-- 자동 updated_at 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성 (이미 존재하면 삭제 후 재생성)
DROP TRIGGER IF EXISTS update_job_postings_updated_at ON job_postings;
CREATE TRIGGER update_job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
