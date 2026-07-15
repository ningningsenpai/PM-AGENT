"""术语库来源抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.normalization.lexicon.models import LexiconManifest

__all__ = ["LexiconProvider"]


class LexiconProvider(ABC):
    """为注册中心提供公共、业务和项目三级术语库。"""

    @abstractmethod
    def load_common(self, version: str | None = None) -> LexiconManifest:
        """加载公共术语库。"""

    @abstractmethod
    def load_domain(self, domain: str, version: str | None = None) -> LexiconManifest:
        """加载指定业务域术语库。"""

    @abstractmethod
    def load_project(self, project_id: str, version: str | None = None) -> LexiconManifest | None:
        """加载项目术语库；项目尚未配置时返回空。"""
