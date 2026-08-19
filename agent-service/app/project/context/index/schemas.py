"""项目索引结构化模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectIndexSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectIndexStorage(ProjectIndexSchema):
    provider: str
    bucket: str
    object_prefix: str
    index_path: str


class ProjectIndexSummary(ProjectIndexSchema):
    total_nodes: int
    active_files: int
    fail_nodes: int


class ProjectIndexFileEntry(ProjectIndexSchema):
    """系统文件或者用户文件在 index.json 中的 payload。"""
    id: int
    storage_uuid: str
    logical_path: str
    file_name: str
    storage_name: str
    minio_path: str
    size_bytes: int
    content_type: str
    status: str
    quick_fingerprint: str
    content_hash: str
    updated_at: datetime
    detail_ref: str | None
    analysis_version: str | None
    module: str | None
    kind: str | None
    file_type: str | None
    language: str | None
    importance: str | None
    summary: str | None
    keywords: list[str] = Field(default_factory=list)


class ProjectIndexUploadFailure(ProjectIndexSchema):
    """上传失败文件在 index.json 的 payload。"""
    file_id: int
    business: str
    logical_path: str
    file_name: str
    storage_name: str
    status: str
    attempts: int
    last_error_code: str | None
    updated_at: datetime


class ProjectIndexSystemReferences(ProjectIndexSchema):
    index: str
    project_specification: str
    long_term_memory: str
    short_term_memory: str
    user_habits: str
    update_journal: str


class ProjectIndexDocument(ProjectIndexSchema):
    """index.json 的完整结构化快照。"""

    project_id: int
    project_name: str
    owner_user_id: int
    schema_version: str
    generated_at: datetime
    updated_at: datetime
    storage: ProjectIndexStorage
    summary: ProjectIndexSummary
    project: list[ProjectIndexFileEntry] = Field(default_factory=list)
    user: list[ProjectIndexFileEntry] = Field(default_factory=list)
    upload_failures: list[ProjectIndexUploadFailure] = Field(default_factory=list)
    system: ProjectIndexSystemReferences
