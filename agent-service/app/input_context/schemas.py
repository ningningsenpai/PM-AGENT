"""归一化与召回共同形成的用户输入上下文协议。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.input_context.normalization import NormalizationResult
from app.input_context.retrieval import RetrievalResult


class UserInputContext(BaseModel):
    """模型首次判断前可用的完整、可信输入上下文。"""

    model_config = ConfigDict(extra="forbid")

    raw_query: str = Field(min_length=1)
    normalization: NormalizationResult | None = None
    retrieval: RetrievalResult
    warnings: list[str] = Field(default_factory=list, max_length=30)
    degraded: bool = False
    learned_entries: list[dict] = Field(default_factory=list, max_length=50)
    learned_terms: list[str] = Field(default_factory=list, max_length=100)
