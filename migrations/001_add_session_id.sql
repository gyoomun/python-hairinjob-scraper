-- job_postings 테이블에 session_id 컬럼 추가
-- 각 스크랩 세션별로 수집된 데이터를 추적하기 위함

ALTER TABLE job_postings
ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES scrape_sessions(id);

-- session_id 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_session_id ON job_postings(session_id);

-- 기존 데이터에 대해서는 session_id를 NULL로 유지
-- (이미 저장된 데이터는 세션 정보가 없음)
