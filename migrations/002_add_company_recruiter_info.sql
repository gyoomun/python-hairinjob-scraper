-- 업체 및 채용담당자 정보 컬럼 추가
-- 헤더에서 추출되는 정보를 저장하기 위함

ALTER TABLE job_postings
ADD COLUMN IF NOT EXISTS company_address TEXT,
ADD COLUMN IF NOT EXISTS company_phone VARCHAR(20),
ADD COLUMN IF NOT EXISTS recruiter_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS recruiter_contact VARCHAR(20);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_company_phone ON job_postings(company_phone);
CREATE INDEX IF NOT EXISTS idx_recruiter_contact ON job_postings(recruiter_contact);

-- 기존 phone 컬럼에 대한 주석
COMMENT ON COLUMN job_postings.phone IS '상세요강 본문에서 추출한 핸드폰번호';
COMMENT ON COLUMN job_postings.company_address IS '헤더의 업체주소';
COMMENT ON COLUMN job_postings.company_phone IS '헤더의 업체 대표 전화번호';
COMMENT ON COLUMN job_postings.recruiter_name IS '헤더의 채용담당자 이름';
COMMENT ON COLUMN job_postings.recruiter_contact IS '헤더의 채용담당자 연락처';
