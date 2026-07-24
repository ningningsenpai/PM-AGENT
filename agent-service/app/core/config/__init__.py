"""在线后端配置导出。"""
from __future__ import annotations

from functools import lru_cache

from .application import (
    DatabaseConfig,
    FileConfig,
    RedisConfig,
    SecurityConfig,
    StorageConfig,
)
from .llm_config import Settings, get_llm_settings

__all__ = [
    "AppConfig",
    "DatabaseConfig",
    "FileConfig",
    "RedisConfig",
    "SecurityConfig",
    "Settings",
    "StorageConfig",
    "get_settings",
]


class AppConfig:
    """PM-Agent 单体后端运行配置。"""

    def __init__(self) -> None:
        self.llm = get_llm_settings()
        self.database = DatabaseConfig.from_env()
        self.redis = RedisConfig.from_env()
        self.security = SecurityConfig.from_env()
        self.storage = StorageConfig.from_env()
        self.file = FileConfig.from_env()


@lru_cache
def get_settings() -> AppConfig:
    return AppConfig()
