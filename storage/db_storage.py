"""
PostgreSQL database storage implementation
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from .base import BaseStorage
from db.config import get_connection_string
from db.queries import batch_insert_jobs, start_scrape_session, complete_scrape_session


class DbStorage(BaseStorage):
    """PostgreSQL 저장 구현"""

    def __init__(self):
        """DB Storage 초기화"""
        self.conn = None
        self.session_id = None

    def save_jobs(self, jobs_list: List[Dict[str, Any]], page_num: int, cookie_idx: int) -> None:
        """
        채용공고 리스트를 DB에 저장 (UPSERT)

        Args:
            jobs_list: 채용공고 데이터 리스트
            page_num: 페이지 번호
            cookie_idx: 쿠키 세트 인덱스
        """
        if not self.conn:
            raise RuntimeError("start_session()을 먼저 호출해야 합니다")

        batch_insert_jobs(self.conn, jobs_list, page_num, cookie_idx, self.session_id)
        self.conn.commit()

    def start_session(self, total_pages: int, num_cookies: int) -> Optional[Any]:
        """
        스크래핑 세션 시작 - DB 연결 및 세션 레코드 생성

        Args:
            total_pages: 전체 페이지 수
            num_cookies: 쿠키 세트 개수

        Returns:
            세션 ID
        """
        self.conn = psycopg2.connect(
            get_connection_string(),
            cursor_factory=RealDictCursor
        )
        self.session_id = start_scrape_session(self.conn, total_pages, num_cookies)
        self.conn.commit()
        print(f"DB 세션 시작 (session_id={self.session_id})")
        return self.session_id

    def complete_session(self, session_id: Optional[Any], total_jobs: int,
                        new_jobs: int, updated_jobs: int) -> None:
        """
        스크래핑 세션 완료 - 세션 레코드 업데이트

        Args:
            session_id: 세션 ID
            total_jobs: 전체 수집 건수
            new_jobs: 신규 등록 건수
            updated_jobs: 업데이트 건수
        """
        if not self.conn or not session_id:
            return

        complete_scrape_session(self.conn, session_id, total_jobs, new_jobs, updated_jobs)
        self.conn.commit()
        print(f"✓ DB 세션 완료 (session_id={session_id})")

    def close(self) -> None:
        """DB 연결 종료"""
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                print(f"DB 연결 종료 중 오류: {e}")
            finally:
                self.conn = None
