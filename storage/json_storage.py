"""
JSON file storage implementation
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from .base import BaseStorage


class JsonStorage(BaseStorage):
    """JSON 파일 저장 구현"""

    def __init__(self, result_dir: str = "results"):
        """
        Args:
            result_dir: JSON 파일 저장 루트 디렉토리
        """
        self.result_dir = result_dir
        self.work_dir = None
        self.session_start_time = None

    def save_jobs(self, jobs_list: List[Dict[str, Any]], page_num: int, cookie_idx: int) -> None:
        """
        채용공고 리스트를 JSON 파일로 저장

        Args:
            jobs_list: 채용공고 데이터 리스트
            page_num: 페이지 번호
            cookie_idx: 쿠키 세트 인덱스
        """
        if not self.work_dir:
            raise RuntimeError("start_session()을 먼저 호출해야 합니다")

        # 쿠키별 폴더 생성
        cookie_work_dir = os.path.join(self.work_dir, f"cookie_{cookie_idx}")
        os.makedirs(cookie_work_dir, exist_ok=True)

        # 페이지별 파일 저장
        page_file = os.path.join(cookie_work_dir, f"page_{page_num:03d}.json")
        with open(page_file, 'w', encoding='utf-8') as f:
            json.dump(jobs_list, f, indent=2, ensure_ascii=False)

    def start_session(self, total_pages: int, num_cookies: int) -> Optional[Any]:
        """
        스크래핑 세션 시작 - 타임스탬프 기반 작업 폴더 생성

        Args:
            total_pages: 전체 페이지 수
            num_cookies: 쿠키 세트 개수

        Returns:
            None (JSON은 세션 ID 불필요)
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.work_dir = os.path.join(self.result_dir, timestamp)
        os.makedirs(self.work_dir, exist_ok=True)
        self.session_start_time = datetime.now()

        print(f"작업 폴더: {self.work_dir}")
        return None

    def complete_session(self, session_id: Optional[Any], total_jobs: int,
                        new_jobs: int, updated_jobs: int) -> None:
        """
        스크래핑 세션 완료 - 통합 JSON 파일 생성

        Args:
            session_id: 사용하지 않음 (JSON은 세션 ID 불필요)
            total_jobs: 전체 수집 건수
            new_jobs: 사용하지 않음 (JSON은 구분 불필요)
            updated_jobs: 사용하지 않음 (JSON은 구분 불필요)
        """
        if not self.work_dir:
            return

        # 모든 쿠키 폴더의 JSON 파일 수집
        all_jobs = []
        for cookie_dir in sorted(os.listdir(self.work_dir)):
            cookie_path = os.path.join(self.work_dir, cookie_dir)
            if not os.path.isdir(cookie_path):
                continue

            for json_file in sorted(os.listdir(cookie_path)):
                if not json_file.endswith('.json'):
                    continue

                json_path = os.path.join(cookie_path, json_file)
                with open(json_path, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
                    all_jobs.extend(jobs)

        # 통합 파일 저장
        all_jobs_file = os.path.join(self.work_dir, "all_jobs.json")
        with open(all_jobs_file, 'w', encoding='utf-8') as f:
            json.dump(all_jobs, f, indent=2, ensure_ascii=False)

        print(f"✓ 통합 파일 저장: {all_jobs_file}")

    def close(self) -> None:
        """리소스 정리 (JSON은 불필요)"""
        pass
