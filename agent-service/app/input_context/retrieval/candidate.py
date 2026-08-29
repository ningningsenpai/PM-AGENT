"""召回链路内部候选模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.input_context.retrieval.schemas import RetrievalEvidence
from app.project_context.file_detail.schemas import FileDetail
from app.project_context.index.schemas import ProjectIndexFileEntry


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """记录候选各评分分量，供回归测试和 Trace 诊断。"""

    high_fields: float = 0.0
    medium_fields: float = 0.0
    low_fields: float = 0.0
    term_source_weight: float = 0.0
    exact_phrase: float = 0.0
    importance: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.high_fields
            + self.medium_fields
            + self.low_fields
            + self.term_source_weight
            + self.exact_phrase
            + self.importance,
            4,
        )


@dataclass(slots=True)
class RetrievalCandidate:
    """在候选生成、排序和证据补充阶段流转的内部对象。"""

    source_type: str
    source_id: str
    title: str
    summary: str
    high_fields: list[str] = field(default_factory=list)
    medium_fields: list[str] = field(default_factory=list)
    low_fields: list[str] = field(default_factory=list)
    logical_path: str | None = None
    file_id: int | None = None
    content_hash: str | None = None
    detail_ref: str | None = None
    importance: str | None = None
    evidence: list[RetrievalEvidence] = field(default_factory=list)
    file_entry: ProjectIndexFileEntry | None = None
    detail: FileDetail | None = None
    source_range: tuple[int, int] | None = None
    score: float = 0.0
    score_breakdown: ScoreBreakdown | None = None
