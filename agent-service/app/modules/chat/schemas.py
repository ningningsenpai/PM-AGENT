"""持久化会话和显式学习接口的输入输出约束。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.core.identifiers import SnowflakeId

EntryKind = Literal["term", "habit", "short_memory", "long_memory"]
EntryStatus = Literal["active", "pending", "invalid"]


class Schema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


ConversationTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class CreateConversation(Schema):
    project_id: SnowflakeId
    title: ConversationTitle | None = None


class RenameConversation(Schema):
    title: ConversationTitle


class SendMessage(Schema):
    content: str = Field(min_length=1, max_length=16000)


class ConversationView(Schema):
    id: SnowflakeId
    project_id: SnowflakeId
    title: str
    learned_message_id: int = Field(ge=0)
    active_run_id: SnowflakeId | None
    created_at: datetime

    @field_serializer("learned_message_id")
    def serialize_cursor(self, value):
        return str(value)


class MessageView(Schema):
    id: SnowflakeId
    role: str
    content: str
    run_id: SnowflakeId
    created_at: datetime
    request_key: str | None = None


class EntryView(Schema):
    id: SnowflakeId
    project_id: SnowflakeId | None
    kind: EntryKind
    content: str
    attributes: dict
    status: EntryStatus
    version: int
    source_message_id: SnowflakeId | None
    expires_at: datetime | None


class UpdateEntry(Schema):
    version: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    status: EntryStatus | None = None
    kind: EntryKind | None = None
    reason: str = Field(min_length=1, max_length=1000)
    expires_at: datetime | None = None


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

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "user" and self.kind not in ("term", "habit"):
            raise ValueError("项目记忆不能写入用户通用范围")
        if self.kind == "term" and (not self.canonical or not self.aliases):
            raise ValueError("词条必须包含标准词和别名")
        return self


class LearningOutput(Schema):
    candidates: list[LearnedCandidate] = Field(default_factory=list, max_length=30)


class GenerateReport(Schema):
    kind: Literal["development", "risk"]


class ReportClaim(Schema):
    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    category: Literal["fact", "risk", "suggestion", "uncertainty"]


class ReportDraft(Schema):
    title: str = Field(min_length=1, max_length=128)
    claims: list[ReportClaim] = Field(min_length=1, max_length=60)
