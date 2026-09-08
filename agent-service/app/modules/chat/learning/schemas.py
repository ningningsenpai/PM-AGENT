"""显式学习的模型候选输出，不等同于已确认的上下文。"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.core.schemas import Schema

from ..context.schemas import EntryKind


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

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "user" and self.kind not in ("term", "habit"):
            raise ValueError("项目记忆不能写入用户通用范围")
        if self.kind == "term" and (not self.canonical or not self.aliases):
            raise ValueError("词条必须包含标准词和别名")
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
