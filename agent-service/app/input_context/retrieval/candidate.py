"""召回链路内部候选模型。"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.input_context.retrieval.schemas import RetrievalEvidence
from app.project_context.file_detail.schemas import FileDetail
from app.project_context.index.schemas import ProjectIndexFileEntry


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
