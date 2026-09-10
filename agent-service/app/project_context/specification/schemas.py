"""项目规范结构化模型。"""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from pydantic import ConfigDict, Field

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema
from app.core.time import ShanghaiDateTime, shanghai_now

RuleT = TypeVar("RuleT", bound="SpecificationRule")


class SpecificationSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class SpecificationSourceRef(SpecificationSchema):
    type: Literal["doc", "code", "project_rule", "conversation", "model_inference"]
    path: str = ""
    file_id: int | None = None
    content_hash: str = ""
    detail_ref: str = ""


class SpecificationRule(SpecificationSchema):
    id: str = Field(min_length=1, max_length=128)
    scope: str
    status: Literal["active", "conflicted", "deprecated", "pending_review"]
    confidence: Literal["high", "medium", "low"]
    source_refs: list[SpecificationSourceRef] = Field(default_factory=list)
    created_at: ShanghaiDateTime
    updated_at: ShanghaiDateTime
    previous_versions: list[dict[str, Any]] = Field(default_factory=list)
    learning_entry_id: SnowflakeId | None = None
    learning_version: int | None = Field(default=None, ge=1)
    human_edited: bool = False
    original_kind: Literal["term", "project_rule"] | None = None


class DevelopmentApproachRule(SpecificationRule):
    rule: str


class TechnicalConstraintRule(SpecificationRule):
    constraint: str


class CodingRule(SpecificationRule):
    rule: str


class DocumentRule(SpecificationRule):
    rule: str


class RiskRule(SpecificationRule):
    rule: str


class DevelopmentStage(SpecificationSchema):
    current_stage: str = ""
    stage_goal: str = ""
    completed: list[str] = Field(default_factory=list)
    next_focus: list[str] = Field(default_factory=list)


class ProjectSpecificationBody(SpecificationSchema):
    """project_specification.json 文件中主体部分的结构化模型"""

    development_stage: DevelopmentStage = Field(default_factory=DevelopmentStage)
    development_approach: list[DevelopmentApproachRule] = Field(default_factory=list)
    technical_constraints: list[TechnicalConstraintRule] = Field(default_factory=list)
    coding_rules: list[CodingRule] = Field(default_factory=list)
    document_rules: list[DocumentRule] = Field(default_factory=list)
    risk_rules: list[RiskRule] = Field(default_factory=list)


class SpecificationChange(SpecificationSchema):
    change_id: str = Field(min_length=1, max_length=128)
    change_type: Literal[
        "created",
        "reinforced",
        "overwritten",
        "conflicted",
        "ignored",
    ]
    target_id: str = ""
    summary: str
    created_at: ShanghaiDateTime
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    source_message_id: SnowflakeId | None = None
    entry_id: SnowflakeId | None = None
    operation_id: str = ""
    request_hash: str = ""


class SpecificationIgnoredItem(SpecificationSchema):
    content: str
    reason: str


class ProjectSpecificationDocument(SpecificationSchema):
    """项目规则文件 project_specification.json 的结构化模型"""

    project_id: SnowflakeId
    schema_version: str = "1.0.0"
    updated_at: ShanghaiDateTime
    project_specification: ProjectSpecificationBody = Field(
        default_factory=ProjectSpecificationBody
    )
    changes: list[SpecificationChange] = Field(default_factory=list)
    ignored_items: list[SpecificationIgnoredItem] = Field(default_factory=list)

    @classmethod
    def empty(cls, project_id: int) -> "ProjectSpecificationDocument":
        return cls(project_id=project_id, updated_at=shanghai_now())


def merge_specifications(
    existing: ProjectSpecificationDocument | None,
    generated: ProjectSpecificationDocument,
) -> ProjectSpecificationDocument:
    """按稳定 ID 合并增量，保留未返回的规则、阶段和其他批次的记录。"""
    if existing is None:
        return generated

    old_body = existing.project_specification
    new_body = generated.project_specification
    body = new_body.model_copy(
        update={
            "development_stage": old_body.development_stage.model_copy(
                update=new_body.development_stage.model_dump(exclude_unset=True)
            ),
            "development_approach": _merge_rules(
                old_body.development_approach,
                new_body.development_approach,
            ),
            "technical_constraints": _merge_rules(
                old_body.technical_constraints,
                new_body.technical_constraints,
            ),
            "coding_rules": _merge_rules(
                old_body.coding_rules,
                new_body.coding_rules,
            ),
            "document_rules": _merge_rules(
                old_body.document_rules,
                new_body.document_rules,
            ),
            "risk_rules": _merge_rules(
                old_body.risk_rules,
                new_body.risk_rules,
            ),
        }
    )
    return generated.model_copy(
        update={
            "project_specification": body,
            "changes": _merge_changes(existing.changes, generated.changes),
            "ignored_items": list(
                {
                    (item.content, item.reason): item
                    for item in [*existing.ignored_items, *generated.ignored_items]
                }.values()
            ),
        }
    )


def _merge_rules(existing: list[RuleT], generated: list[RuleT]) -> list[RuleT]:
    merged = {item.id: item for item in existing}
    merged.update(
        {
            item.id: item
            for item in generated
            if not (
                item.id in merged
                and (
                    merged[item.id].human_edited
                    or any(
                        ref.type == "conversation"
                        for ref in merged[item.id].source_refs
                    )
                )
            )
        }
    )
    return list(merged.values())


def _merge_changes(
    existing: list[SpecificationChange],
    generated: list[SpecificationChange],
) -> list[SpecificationChange]:
    merged = {item.change_id: item for item in existing}
    merged.update({item.change_id: item for item in generated})
    return list(merged.values())
