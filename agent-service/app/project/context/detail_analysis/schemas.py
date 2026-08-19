from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

__all__ = [
    "FileAnalysisRequest",
    "FileAnalysisResult",
    "FileDetail",
    "FileDetailSemanticOutput",
    "FileRuleCandidate",
]

Keyword = Annotated[str, Field(min_length=1, max_length=128)]
EvidenceText = Annotated[str, Field(min_length=1, max_length=500)]


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


class FileRuleCandidate(BaseModel):
    """从单文件中提取、等待项目级规范确认的结构化规则候选。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Literal[
        "development_approach",
        "technical_constraint",
        "coding_rule",
        "document_rule",
        "risk_rule",
    ]
    text: str = Field(min_length=1, max_length=1000)
    confidence: Literal["high", "medium", "low"]
    evidence: list[EvidenceText] = Field(default_factory=list, max_length=20)


class FileDetailSemanticOutput(BaseModel):
    """限制模型只生成文件语义，身份和控制字段由服务端补充。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module: str = Field(max_length=128)
    kind: str = Field(max_length=64)
    file_type: str = Field(max_length=64)
    language: str = Field(max_length=64)
    importance: Literal["high", "medium", "low"]
    summary: str = Field(max_length=4000)
    keywords: list[Keyword] = Field(max_length=50)
    role: str = Field(max_length=2000)
    content_slices: list[dict[str, Any]] = Field(max_length=50)
    related_topics: list[Keyword] = Field(max_length=50)
    related_files: list[dict[str, Any]] = Field(max_length=50)
    risk_flags: list[Any] = Field(max_length=50)
    sensitive_flags: list[Any] = Field(max_length=50)
    evidence: list[Any] = Field(max_length=50)
    parser: dict[str, Any]
    rule_candidates: list[FileRuleCandidate] = Field(
        default_factory=list, max_length=100
    )


class FileDetail(BaseModel):
    """服务端组装的完整文件详情和索引投影来源。"""

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
    rule_candidates: list[FileRuleCandidate] = Field(default_factory=list)


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
