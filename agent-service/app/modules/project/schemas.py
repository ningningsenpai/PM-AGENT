"""项目请求与响应模型。"""

from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema
from app.core.time import ShanghaiDateTime
from app.modules.project.domain import ProjectRecordStatus


class ProjectSchema(Schema):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class CreateProjectRequest(ProjectSchema):
    project_name: str = Field(min_length=1, max_length=128)

    @field_validator("project_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("项目名称不能为空")
        return normalized


class ProjectResponse(ProjectSchema):
    id: SnowflakeId
    project_name: str
    status: str
    record_status: str = ProjectRecordStatus.ENABLED.value
    revision: int = 0
    published_revision: int = 0
    created_at: ShanghaiDateTime
    updated_at: ShanghaiDateTime

    @field_validator("revision", "published_revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: int | None) -> int:
        return 0 if value is None else value


def to_response(project) -> ProjectResponse:
    return ProjectResponse.model_validate(project)
