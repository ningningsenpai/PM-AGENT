"""文件详情 MQ 事件、完整详情文档和 Java 回调模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Java 事件与回调信封使用 camelCase。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class FileParsingEvent(CamelModel):
    event_id: str = Field(min_length=1, max_length=64)
    batch_id: int | None = Field(default=None, gt=0)
    project_id: int = Field(gt=0)
    file_id: int = Field(gt=0)
    storage_uuid: str = Field(min_length=1, max_length=32)
    storage_name: str = Field(min_length=1, max_length=255)
    logical_path: str = Field(min_length=1, max_length=512)
    minio_path: str = Field(min_length=1, max_length=512)
    size_bytes: int = Field(ge=0)
    content_type: str = Field(min_length=1, max_length=128)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    source_url: str = Field(min_length=1)
    read_url_refresh_url: str = Field(min_length=1)
    existing_detail_url: str | None = None
    detail_ref: str = Field(min_length=1, max_length=512)
    analysis_version: str = Field(min_length=1, max_length=64)
    callback_url: str = Field(min_length=1)
    trace_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime


class SourceRange(BaseModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> "SourceRange":
        if self.end_line < self.start_line:
            raise ValueError("内容切片结束行不能小于开始行")
        return self


class ContentSlice(BaseModel):
    slice_id: str = Field(min_length=1, max_length=128)
    type: Literal["api", "service", "component", "config", "model", "test", "doc", "other"]
    summary: str = Field(min_length=1, max_length=1000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    entities: list[str] = Field(default_factory=list, max_length=64)
    source_range: SourceRange | None = None


class RelatedFile(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    relation: Literal[
        "service_dependency",
        "api_dependency",
        "component_dependency",
        "config_dependency",
        "test_target",
        "doc_reference",
        "other",
    ]


class Evidence(BaseModel):
    source: Literal["file_content", "file_tree_node", "existing_file_detail_json"]
    quote: str = Field(min_length=1, max_length=300)


class PreviousVersion(BaseModel):
    content_hash: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=1000)
    changed_at: datetime
    reason: str = Field(min_length=1, max_length=500)


class ParserMetadata(BaseModel):
    strategy: str = Field(min_length=1, max_length=64)
    parser_version: str = Field(min_length=1, max_length=128)
    sampled: bool
    parsed_lines: int = Field(ge=0, le=1_000_000)


class FileDetailDocument(BaseModel):
    """完整详情文档；前六个语义字段同时作为 index.json 的直接投影。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    project_id: int = Field(gt=0)
    file_id: int = Field(gt=0)
    schema_version: str = Field(min_length=1, max_length=32)
    analysis_version: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    updated_at: datetime
    storage_uuid: str = Field(min_length=1, max_length=32)
    storage_name: str = Field(min_length=1, max_length=255)
    detail_ref: str = Field(min_length=1, max_length=512)
    original_path: str = Field(min_length=1, max_length=512)
    minio_path: str = Field(min_length=1, max_length=512)
    size_bytes: int = Field(ge=0)
    content_type: str = Field(min_length=1, max_length=128)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    module: str = Field(min_length=1, max_length=128)
    kind: str = Field(min_length=1, max_length=64)
    file_type: str = Field(min_length=1, max_length=128)
    language: str = Field(min_length=1, max_length=32)
    status: Literal["active", "deleted", "pending_review"]
    importance: Literal["high", "medium", "low"]
    summary: str = Field(min_length=1, max_length=1000)
    keywords: list[str] = Field(min_length=1, max_length=32)
    role: str = Field(min_length=1, max_length=1000)
    content_slices: list[ContentSlice] = Field(default_factory=list, max_length=64)
    related_topics: list[str] = Field(default_factory=list, max_length=32)
    related_files: list[RelatedFile] = Field(default_factory=list, max_length=64)
    risk_flags: list[str] = Field(default_factory=list, max_length=32)
    sensitive_flags: list[str] = Field(default_factory=list, max_length=32)
    evidence: list[Evidence] = Field(default_factory=list, max_length=32)
    previous_versions: list[PreviousVersion] = Field(default_factory=list, max_length=20)
    parser: ParserMetadata


class FileAnalysisResult(CamelModel):
    event_id: str
    batch_id: int | None = None
    content_hash: str
    analysis_version: str
    status: Literal["success", "failed"]
    detail: FileDetailDocument | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_result(self) -> "FileAnalysisResult":
        if self.status == "success" and self.detail is None:
            raise ValueError("成功结果必须包含完整详情文档")
        if self.status == "failed" and self.detail is not None:
            raise ValueError("失败结果不能携带详情文档")
        return self
