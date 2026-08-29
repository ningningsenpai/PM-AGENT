"""用户输入理解与项目上下文召回模块。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from app.input_context.normalization import (
    NormalizationRequest,
    NormalizationResult,
    NormalizationService,
    TermMatch,
    create_default_normalization_service,
)

_LAZY_EXPORTS = {
    "InputContextRetrievalService": (
        "app.input_context.retrieval",
        "InputContextRetrievalService",
    ),
    "RetrievalEvidence": ("app.input_context.retrieval", "RetrievalEvidence"),
    "RetrievalHit": ("app.input_context.retrieval", "RetrievalHit"),
    "RetrievalQuery": ("app.input_context.retrieval", "RetrievalQuery"),
    "RetrievalResult": ("app.input_context.retrieval", "RetrievalResult"),
    "UserInputContext": ("app.input_context.schemas", "UserInputContext"),
    "UserInputContextService": (
        "app.input_context.service",
        "UserInputContextService",
    ),
}

__all__ = [
    "InputContextRetrievalService",
    "NormalizationRequest",
    "NormalizationResult",
    "NormalizationService",
    "RetrievalEvidence",
    "RetrievalHit",
    "RetrievalQuery",
    "RetrievalResult",
    "TermMatch",
    "UserInputContext",
    "UserInputContextService",
    "create_default_normalization_service",
]


def __getattr__(name: str) -> Any:
    """延迟加载召回边界，避免旧归一化导入被迫加载在线依赖。"""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"模块 {__name__!r} 不包含属性 {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
