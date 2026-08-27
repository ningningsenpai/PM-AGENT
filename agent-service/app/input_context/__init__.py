"""用户输入理解与项目上下文召回模块。"""

from app.input_context.normalization import (
    NormalizationRequest,
    NormalizationResult,
    NormalizationService,
    TermMatch,
    create_default_normalization_service,
)
from app.input_context.retrieval import (
    InputContextRetrievalService,
    RetrievalEvidence,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
)

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
    "create_default_normalization_service",
]
