import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5433'),
    'database': os.getenv('DB_NAME', 'hairinjob'),
    'user': os.getenv('DB_USER', 'hairinjob_user'),
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
