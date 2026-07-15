"""项目上下文模型数据结构。"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ProjectContextModelConfig",
    "ProjectContextModelResponse",
]


@dataclass(frozen=True)
class ProjectContextModelConfig:
    """项目上下文模型配置。"""

    provider: str
    base_url: str
    model_name: str
    timeout_seconds: float
    context_size: int
    concurrency: int


@dataclass(frozen=True)
class ProjectContextModelResponse:
    """项目上下文模型统一响应。"""

    provider: str
    model: str
    content: str
    done: bool
    finish_reason: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
