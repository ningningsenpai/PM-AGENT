from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema
from app.core.time import ShanghaiDateTime

__all__ = [
    "FileDetail",
    "FileDetailSemanticOutput",
    "FileRuleCandidate",
    "FileSemanticAnalysisRequest",
    "FileSemanticAnalysisResult",
]

Keyword = Annotated[str, Field(min_length=1, max_length=128)]
EvidenceText = Annotated[str, Field(min_length=1, max_length=500)]


class FileSemanticAnalysisRequest(Schema):
    """文件语义分析所需的完整元数据。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )

    user_id: SnowflakeId
    project_id: SnowflakeId
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


class FileRuleCandidate(Schema):
    """由单文件语义分析生成、等待项目级规范确认的结构化规则候选。"""

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


class FileDetailSemanticOutput(Schema):
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
    project_facts: list[dict[str, Any]] = Field(default_factory=list, max_length=40)

    @field_validator("related_files", mode="before")
    @classmethod
    def normalize_related_file_paths(cls, value: Any) -> Any:
        """兼容模型的路径字符串简写，存储时仍统一为对象数组。"""
        if not isinstance(value, list):
            return value
        return [
            {"path": item} if isinstance(item, str) and item.strip() else item
            for item in value
        ]


class FileDetail(Schema):
    """服务端组装的完整文件详情和索引投影来源。"""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: str
    project_id: SnowflakeId
    file_id: int
    schema_version: str
    generated_at: ShanghaiDateTime
    updated_at: ShanghaiDateTime
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
    project_facts: list[dict[str, Any]] = Field(default_factory=list)


class FileSemanticAnalysisResult(Schema):
    """文件语义分析返回的结构化结果或失败信息。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
    )

    project_id: SnowflakeId
    file_id: int
    content_hash: str
    status: Literal["success", "failed"]
    detail: FileDetail | None = None
    error_code: str | None = None
    error_message: str | None = None
