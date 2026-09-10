"""项目上下文召回输入和输出协议。"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from app.core.schemas import Schema
from app.core.time import ShanghaiDateTime

RetrievalFocus = Literal[
    "auto",
    "files",
    "specification",
    "memory",
    "habits",
    "changes",
]
EvidenceLevel = Literal["auto", "summary", "source"]
RetrievalSourceType = Literal[
    "source_file",
    "file_detail",
    "project_specification",
    "long_term_memory",
    "short_term_memory",
    "user_habit",
    "update_journal",
]


class RetrievalSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class RetrievalQuery(RetrievalSchema):
    """一次项目上下文召回请求。"""

    query: str = Field(min_length=1, max_length=2000)
    focus: RetrievalFocus = "auto"
    evidence_level: EvidenceLevel = "auto"
    limit: int = Field(default=5, ge=1, le=8)


class RetrievalEvidence(RetrievalSchema):
    """可安全回填模型的单条证据。"""

    text: str = Field(min_length=1, max_length=12000)
    logical_path: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    redacted: bool = False
    truncated: bool = False
    kind: Literal["source", "summary", "user_statement"] = "summary"


class RetrievalHit(RetrievalSchema):
    """完成排序和补证后的召回命中。"""

    source_type: RetrievalSourceType
    source_id: str
    title: str
    summary: str
    score: float = Field(ge=0)
    logical_path: str | None = None
    file_id: int | None = None
    content_hash: str | None = None
    detail_ref: str | None = None
    importance: str | None = None
    evidence: list[RetrievalEvidence] = Field(default_factory=list, max_length=10)


class RetrievalResult(RetrievalSchema):
    """前置上下文和 Agent 工具共用的召回结果。"""

    query: str
    normalized_terms: list[str] = Field(default_factory=list, max_length=200)
    index_updated_at: ShanghaiDateTime | None = None
    hits: list[RetrievalHit] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    degraded: bool = False
    no_evidence: bool = False
