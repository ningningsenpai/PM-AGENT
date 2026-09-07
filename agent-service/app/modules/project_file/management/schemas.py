"""项目文件请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from app.core.identifiers import SnowflakeId


class FileSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UpdateProjectFilePathRequest(FileSchema):
    relative_path: str = Field(min_length=1, max_length=512)
    source_mtime_ms: int = Field(ge=0)
    lock_version: int = Field(ge=0)


class ProjectFileResponse(FileSchema):
    id: int
    project_id: SnowflakeId
    business_code: str
    relative_path: str
    file_name: str
    storage_name: str
    minio_path: str
    extension: str | None
    content_type: str
    size_bytes: int
    source_mtime_ms: int
    quick_fingerprint: str
    content_hash: str
    status: str
    upload_status: str
    parse_attempts: int
    detail_ref: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_failed_at: datetime | None = None
    lock_version: int
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def analysis_status(self) -> str:
        if self.upload_status != "success" or self.status != "active":
            return "unavailable"
        if self.last_error_code and self.last_error_code.startswith("FILE_DETAIL"):
            return "failed"
        return "success" if self.detail_ref else "pending"


class ProjectFileUploadResponse(FileSchema):
    file_id: int
    relative_path: str
    file_name: str
    success: bool
    status: str
    upload_status: str
    error_code: str | None = None
    error_message: str | None = None


class FileReadUrlResponse(FileSchema):
    file_id: int
    file_name: str
    url: str
    expires_at: datetime


def to_file_response(file) -> ProjectFileResponse:
    return ProjectFileResponse.model_validate(file)
