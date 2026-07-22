
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

__all__ = [
    "FileAnalysisRequest",
    "FileAnalysisResult",
    "FileDetail",
]


class FileAnalysisRequest(BaseModel):
    """文件分析接口接收的完整元数据。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )

    user_id: int
    project_id: int
    business: str
    file_id: int
    filename: str
    file_url: str
    file_type: str
    storage_uuid: str
    storage_name: str
    detail_ref: str
    original_path: str
    minio_path: str
    size_bytes: int
    content_type: str
    content_hash: str
    analysis_version: str


class FileDetail(BaseModel):
    """文件详情模型，约束模型输出并保留索引补全所需字段。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: str
    project_id: int
    file_id: int
    schema_version: str
    analysis_version: str
    generated_at: datetime
    updated_at: datetime
    storage_uuid: str
    storage_name: str
    detail_ref: str
    original_path: str
    minio_path: str
    size_bytes: int
    content_type: str
    content_hash: str
    module: str
    kind: str
    file_type: str
    language: str
    status: str
    importance: str
    summary: str
    keywords: list[str]
    role: str
    content_slices: list[dict[str, Any]]
    related_topics: list[str]
    related_files: list[dict[str, Any]]
    risk_flags: list[Any]
    sensitive_flags: list[Any]
    evidence: list[Any]
    previous_versions: list[dict[str, Any]]
    parser: dict[str, Any]


class FileAnalysisResult(BaseModel):
    """文件分析接口返回的结构化结果或文件级失败信息。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )

    project_id: int
    file_id: int
    content_hash: str
    analysis_version: str
    status: Literal["success", "failed"]
    detail: FileDetail | None = None
    error_code: str | None = None
    error_message: str | None = None
