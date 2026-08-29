"""旧归一化导入路径的兼容门面。"""

from app.input_context.normalization import (
    NormalizationRequest,
    NormalizationResult,
    NormalizationService,
    TermMatch,
    create_default_normalization_service,
)

__all__ = [
    "NormalizationRequest",
    "NormalizationResult",
    "NormalizationService",
    "TermMatch",
    "create_default_normalization_service",
]
