"""
Base storage interface for scraper data persistence
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStorage(ABC):
    """추상 Storage 인터페이스"""

    @abstractmethod
    def save_jobs(self, jobs_list: List[Dict[str, Any]], page_num: int, cookie_idx: int) -> None:
        """
        채용공고 리스트 저장

        Args:
            jobs_list: 채용공고 데이터 리스트
            page_num: 페이지 번호
            cookie_idx: 쿠키 세트 인덱스
        """
        pass

    @abstractmethod
    def start_session(self, total_pages: int, num_cookies: int) -> Optional[Any]:
        """
        스크래핑 세션 시작 기록

        Args:
            total_pages: 전체 페이지 수
            num_cookies: 쿠키 세트 개수

        Returns:
            세션 ID (DB의 경우) 또는 None (JSON의 경우)
        """
        pass

    @abstractmethod
    def complete_session(self, session_id: Optional[Any], total_jobs: int,
                        new_jobs: int, updated_jobs: int) -> None:
        """
        스크래핑 세션 완료 기록

        Args:
            session_id: 세션 ID (DB의 경우)
            total_jobs: 전체 수집 건수
            new_jobs: 신규 등록 건수
            updated_jobs: 업데이트 건수
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """리소스 정리 (DB 연결 종료 등)"""
        pass
