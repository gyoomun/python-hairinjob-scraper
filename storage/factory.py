"""
Storage factory for creating appropriate storage instances
"""
from typing import List
from .base import BaseStorage
from .json_storage import JsonStorage
from .db_storage import DbStorage


class CompositeStorage(BaseStorage):
    """여러 Storage를 동시에 사용하는 복합 Storage"""

    def __init__(self, storages: List[BaseStorage]):
        """
        Args:
            storages: 사용할 Storage 인스턴스 리스트
        """
        self.storages = storages

    def save_jobs(self, jobs_list, page_num, cookie_idx):
        """모든 Storage에 동시 저장"""
        for storage in self.storages:
            storage.save_jobs(jobs_list, page_num, cookie_idx)

    def start_session(self, total_pages, num_cookies):
        """모든 Storage의 세션 시작"""
        session_ids = []
        for storage in self.storages:
            session_id = storage.start_session(total_pages, num_cookies)
            session_ids.append(session_id)
        # DB 세션 ID가 있으면 반환, 없으면 None
        return next((sid for sid in session_ids if sid is not None), None)

    def complete_session(self, session_id, total_jobs, new_jobs, updated_jobs):
        """모든 Storage의 세션 완료"""
        for storage in self.storages:
            storage.complete_session(session_id, total_jobs, new_jobs, updated_jobs)

    def close(self):
        """모든 Storage 리소스 정리"""
        for storage in self.storages:
            storage.close()


def create_storage(storage_type: str, result_dir: str = "results") -> BaseStorage:
    """
    --storage 인자에 따라 적절한 Storage 객체 생성

    Args:
        storage_type: 'json', 'db', 또는 'both'
        result_dir: JSON 저장 시 사용할 디렉토리

    Returns:
        BaseStorage 인스턴스

    Raises:
        ValueError: 지원하지 않는 storage_type
    """
    if storage_type == 'json':
        return JsonStorage(result_dir=result_dir)
    elif storage_type == 'db':
        return DbStorage()
    elif storage_type == 'both':
        return CompositeStorage([
            JsonStorage(result_dir=result_dir),
            DbStorage()
        ])
    else:
        raise ValueError(f"지원하지 않는 storage 타입: {storage_type}")
