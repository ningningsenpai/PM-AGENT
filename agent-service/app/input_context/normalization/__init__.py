"""输入上下文模块对既有归一化能力的稳定适配入口。"""

from app.normalization import (
    NormalizationRequest,
    NormalizationResult,
    NormalizationService,
    TermMatch,
    create_default_normalization_service,
)
from app.normalization.lexicon.json_provider import LexiconLoadError
from app.normalization.preprocessing import TextNormalizer

__all__ = [
    "LexiconLoadError",
    "NormalizationRequest",
    "NormalizationResult",
    "NormalizationService",
    "TermMatch",
    "TextNormalizer",
    "create_default_normalization_service",
]
