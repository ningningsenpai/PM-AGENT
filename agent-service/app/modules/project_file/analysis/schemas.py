"""项目文件批次分析响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.schemas import Schema

__all__ = [
    "ProjectFileAnalysisBatchResult",
    "ProjectFileAnalysisFailure",
    "ProjectFileParseRecovery",
]


class AnalysisResponseSchema(Schema):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )


class ProjectFileAnalysisFailure(AnalysisResponseSchema):
    file_id: int
    relative_path: str
    error_code: str
    error_message: str


class ProjectFileAnalysisBatchResult(AnalysisResponseSchema):
    run_id: str | None = None
    status: Literal["success", "partial"]
    candidate_count: int
    success_count: int
    failure_count: int
    failures: list[ProjectFileAnalysisFailure] = Field(default_factory=list)
    specification_status: Literal["updated", "kept", "failed"]
    index_status: Literal["updated", "failed"]


class ProjectFileParseRecovery(AnalysisResponseSchema):
    run_id: str | None
    status: Literal["absent", "running", "success", "failed"]
    retryable: bool
    retry_mode: Literal["same_key", "new_key"] | None
    lease_until: datetime | None
    result: ProjectFileAnalysisBatchResult | None
    error: str | None
