"""
Storage module for HairinJob scraper
Supports multiple storage backends: JSON, PostgreSQL, or both
"""
from .base import BaseStorage
from .json_storage import JsonStorage
from .db_storage import DbStorage
from .factory import create_storage

__all__ = ['BaseStorage', 'JsonStorage', 'DbStorage', 'create_storage']
