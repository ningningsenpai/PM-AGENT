# 项目上下文模型配置读取。
from __future__ import annotations

import os
from dataclasses import dataclass

from .schemas import ProjectContextModelConfig

__all__ = ["load_model_config"]


_DEFAULT_PROVIDER = "ollama"
_DEFAULT_MODEL_NAME = "qwen2.5:7b-instruct"
_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_CONTEXT_SIZE = 4096
_DEFAULT_CONCURRENCY = 1


def load_model_config() -> ProjectContextModelConfig:
    """从环境变量读取项目上下文模型配置。"""
    return ProjectContextModelConfig(
        provider=os.getenv("PROJECT_CONTEXT_MODEL_PROVIDER", _DEFAULT_PROVIDER),
        base_url=os.getenv("PROJECT_CONTEXT_MODEL_BASE_URL", _DEFAULT_BASE_URL).rstrip("/"),
        model_name=os.getenv("PROJECT_CONTEXT_MODEL_NAME", _DEFAULT_MODEL_NAME),
        timeout_seconds=float(os.getenv("PROJECT_CONTEXT_MODEL_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS))),
        context_size=int(os.getenv("PROJECT_CONTEXT_MODEL_CONTEXT_SIZE", str(_DEFAULT_CONTEXT_SIZE))),
        concurrency=int(os.getenv("PROJECT_CONTEXT_MODEL_CONCURRENCY", str(_DEFAULT_CONCURRENCY))),
    )
