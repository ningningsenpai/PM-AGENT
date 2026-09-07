"""项目文件批次分析响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

__all__ = ["ProjectFileAnalysisBatchResult", "ProjectFileAnalysisFailure"]


class AnalysisResponseSchema(BaseModel):
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
