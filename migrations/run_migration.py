#!/usr/bin/env python3
"""
마이그레이션 실행 스크립트
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_db_connection

def run_migration(migration_file):
    """마이그레이션 SQL 파일 실행"""
    print(f"마이그레이션 실행 중: {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        print(f"✓ 마이그레이션 완료: {migration_file}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python migrations/run_migration.py <migration_file.sql>")
        print("\n예시:")
        print("  python migrations/run_migration.py migrations/001_add_session_id.sql")
        sys.exit(1)

    migration_file = sys.argv[1]

    if not os.path.exists(migration_file):
        print(f"✗ 오류: '{migration_file}' 파일을 찾을 수 없습니다.")
        sys.exit(1)

    try:
        run_migration(migration_file)
    except Exception as e:
        print(f"✗ 마이그레이션 실패: {e}")
        sys.exit(1)
