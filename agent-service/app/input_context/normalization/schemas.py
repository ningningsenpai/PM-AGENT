"""内容归一化输入、输出和命中结果模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.input_context.normalization.lexicon.models import (
    LexiconScope,
    LexiconVersionSet,
)

__all__ = ["NormalizationRequest", "NormalizationResult", "TermMatch"]


class NormalizationRequest(BaseModel):
    """一次内容归一化请求。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    tenant_id: int = 0
    project_id: str | None = None
    domain: str = "project_management"


class TermMatch(BaseModel):
    """一个已经完成标准术语映射的命中结果。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    term_id: str
    canonical: str
    alias: str
    matched_text: str
    category: str
    tags: tuple[str, ...] = Field(default_factory=tuple)
    start: int
    end: int
    cleaned_start: int
    cleaned_end: int
    source: str
    lexicon_id: str
    scope: LexiconScope


class NormalizationResult(BaseModel):
    """归一化流水线的结构化结果。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_text: str
    cleaned_text: str
    lexicon_version_set: LexiconVersionSet
    normalized_terms: tuple[str, ...] = Field(default_factory=tuple)
    matches: tuple[TermMatch, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    stage_durations_ms: dict[str, float] = Field(default_factory=dict)
