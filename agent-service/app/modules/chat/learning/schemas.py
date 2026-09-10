"""显式学习的模型候选输出，不等同于已确认的上下文。"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.core.schemas import Schema

from ..context.schemas import EntryKind

LearningTargetFile = Literal[
    "project_specification.json",
    "short_term_memory.json",
    "long_term_memory.json",
    "user_habits/work.json",
    "user_habits/thinking.json",
    "user_habits/specification.json",
    "user_habits/tooling.json",
    "user_habits/life.json",
]
RuleSection = Literal[
    "development_approach",
    "technical_constraints",
    "coding_rules",
    "document_rules",
    "risk_rules",
]


class LearnedCandidate(Schema):
    kind: EntryKind
    scope: Literal["user", "project"]
    key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    source_message_id: str
    source_quote: str = Field(min_length=1, max_length=1000)
    confirmed: bool = False
    replaces_entry_id: str | None = None
    invalidate: bool = False
    aliases: list[str] = Field(default_factory=list, max_length=20)
    canonical: str | None = Field(default=None, max_length=200)
    expires_at: datetime | None = None
    conditions: list[str] = Field(default_factory=list, max_length=20)
    related_entry_ids: list[str] = Field(default_factory=list, max_length=30)
    coexist_reason: str | None = Field(default=None, max_length=1000)
    # 模型只提供本轮局部分组，真实条目编号由服务端分配和关联。
    coexist_group: str | None = Field(default=None, min_length=1, max_length=64)
    target_file: LearningTargetFile | None = None
    target_section: RuleSection | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "user" and self.kind not in ("term", "habit"):
            raise ValueError("项目记忆不能写入用户通用范围")
        if self.kind == "term" and (not self.canonical or not self.aliases):
            raise ValueError("词条必须包含标准词和别名")
        expected = {
            "short_memory": "short_term_memory.json",
            "long_memory": "long_term_memory.json",
            "project_rule": "project_specification.json",
        }.get(self.kind)
        if self.kind == "term":
            expected = (
                "user_habits/specification.json"
                if self.scope == "user"
                else "project_specification.json"
            )
        if self.kind == "habit" and self.target_file is None:
            expected = "user_habits/work.json"
        if self.target_file is None:
            self.target_file = expected
        if expected and self.target_file != expected:
            raise ValueError("候选类型与目标固定文件不一致")
        if self.kind == "habit" and not self.target_file.startswith("user_habits/"):
            raise ValueError("用户习惯必须写入用户习惯固定文件")
        if (
            self.target_section is not None
            and self.target_file != "project_specification.json"
        ):
            raise ValueError("只有项目规范候选可以指定规范分区")
        return self


class LearningOutput(Schema):
    candidates: list[LearnedCandidate] = Field(default_factory=list, max_length=30)


class DraftCandidate(Schema):
    id: str = Field(pattern=r"^[0-9]+$")
    proposal: LearnedCandidate


class EditDraft(Schema):
    version: int = Field(ge=1)
    candidates: list[DraftCandidate] = Field(max_length=30)
    reason: str = Field(min_length=1, max_length=1000)


class RefineDraft(Schema):
    version: int = Field(ge=1)
    candidate_ids: list[str] = Field(min_length=1, max_length=30)
    feedback: str = Field(min_length=1, max_length=4000)


class ConfirmDraft(Schema):
    version: int = Field(ge=1)
    candidate_ids: list[str] = Field(max_length=30)


class DraftVersion(Schema):
    version: int = Field(ge=1)
