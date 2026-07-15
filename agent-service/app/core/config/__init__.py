"""Agent 服务配置导出。"""
from __future__ import annotations

from functools import lru_cache

from .llm_config import Settings, get_llm_settings

__all__ = ["get_settings", "Settings"]


class AppConfig:
    """Agent 服务配置。"""

    def __init__(self) -> None:
        self.llm = get_llm_settings()


@lru_cache
def get_settings() -> AppConfig:
    return AppConfig()
