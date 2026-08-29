"""用户输入归一化能力的稳定公开入口。"""

from app.input_context.normalization.lexicon.json_provider import LexiconLoadError
from app.input_context.normalization.preprocessing import TextNormalizer
from app.input_context.normalization.schemas import (
    NormalizationRequest,
    NormalizationResult,
    TermMatch,
)
from app.input_context.normalization.service import (
    NormalizationService,
    create_default_normalization_service,
)

__all__ = [
    "LexiconLoadError",
    "NormalizationRequest",
    "NormalizationResult",
    "NormalizationService",
    "TermMatch",
    "TextNormalizer",
    "create_default_normalization_service",
]
