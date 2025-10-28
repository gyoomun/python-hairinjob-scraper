import json
from psycopg2.extras import execute_values

def batch_insert_jobs(conn, jobs_list, page_num, cookie_idx, session_id=None):
    """대량 저장 (UPSERT)"""
    if not jobs_list:
        return

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
            job.get('company_address'),
            job.get('company_phone'),
            job.get('recruiter_name'),
            job.get('recruiter_contact'),
            page_num,
            cookie_idx,
            session_id
        ))

    execute_values(cursor, '''
        INSERT INTO job_postings
        (idx, company_name, title, detail_url, positions,
         location, salary, gender, deadline, grade,
         priority_badge, special_badges, phone,
         company_address, company_phone, recruiter_name, recruiter_contact,
         page_number, cookie_set, session_id)
        VALUES %s
        ON CONFLICT (idx) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            title = EXCLUDED.title,
            positions = EXCLUDED.positions,
            location = EXCLUDED.location,
            salary = EXCLUDED.salary,
            gender = EXCLUDED.gender,
            deadline = EXCLUDED.deadline,
            grade = EXCLUDED.grade,
            priority_badge = EXCLUDED.priority_badge,
            special_badges = EXCLUDED.special_badges,
            phone = COALESCE(EXCLUDED.phone, job_postings.phone),
            company_address = COALESCE(EXCLUDED.company_address, job_postings.company_address),
            company_phone = COALESCE(EXCLUDED.company_phone, job_postings.company_phone),
            recruiter_name = COALESCE(EXCLUDED.recruiter_name, job_postings.recruiter_name),
            recruiter_contact = COALESCE(EXCLUDED.recruiter_contact, job_postings.recruiter_contact),
            session_id = COALESCE(EXCLUDED.session_id, job_postings.session_id),
            updated_at = NOW()
    ''', values)

def start_scrape_session(conn, total_pages, num_cookies):
    """스크래핑 세션 시작 기록"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scrape_sessions (total_pages, num_cookies, status)
        VALUES (%s, %s, 'running')
        RETURNING id
    ''', (total_pages, num_cookies))
    return cursor.fetchone()['id']

def complete_scrape_session(conn, session_id, total_jobs, new_jobs, updated_jobs):
    """스크래핑 세션 완료 기록"""
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

def get_total_jobs_count(conn):
    """전체 채용공고 개수"""
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM job_postings')
    return cursor.fetchone()['count']

def get_latest_session_id(conn):
    """가장 최근 세션 ID 조회"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT MAX(id) as latest_id
        FROM scrape_sessions
    ''')
    result = cursor.fetchone()
    return result['latest_id'] if result else None

def get_all_detail_urls(conn):
    """가장 최근 세션의 채용공고 상세페이지 URL 조회"""
    cursor = conn.cursor()

    # 가장 최근 세션 ID 조회
    latest_session_id = get_latest_session_id(conn)

    if not latest_session_id:
        print("⚠️  스크랩 세션이 없습니다.")
        return []

    print(f"가장 최근 세션 ID: {latest_session_id}")

    cursor.execute('''
        SELECT idx, detail_url, company_name, title, session_id
        FROM job_postings
        WHERE detail_url IS NOT NULL
          AND session_id = %s
        ORDER BY idx
    ''', (latest_session_id,))
    return cursor.fetchall()

def get_jobs_by_session(conn, session_id):
    """특정 세션에서 스크랩된 채용공고 조회"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT *
        FROM job_postings
        WHERE session_id = %s
        ORDER BY scraped_at DESC
    ''', (session_id,))
    return cursor.fetchall()

def get_session_stats(conn, session_id):
    """특정 세션의 통계 정보 조회"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            s.id,
            s.started_at,
            s.completed_at,
            s.total_pages,
            s.total_jobs,
            s.new_jobs,
            s.updated_jobs,
            s.num_cookies,
            s.status,
            COUNT(j.idx) as actual_count
        FROM scrape_sessions s
        LEFT JOIN job_postings j ON j.session_id = s.id
        WHERE s.id = %s
        GROUP BY s.id
    ''', (session_id,))
    return cursor.fetchone()

def get_all_sessions(conn):
    """모든 스크랩 세션 목록 조회"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            s.id,
            s.started_at,
            s.completed_at,
            s.status,
            s.total_jobs,
            COUNT(j.idx) as job_count
        FROM scrape_sessions s
        LEFT JOIN job_postings j ON j.session_id = s.id
        GROUP BY s.id
        ORDER BY s.started_at DESC
    ''')
    return cursor.fetchall()
