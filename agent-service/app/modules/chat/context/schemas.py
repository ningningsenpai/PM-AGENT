"""学习上下文的类型、查询与纠正契约。"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema

EntryKind = Literal["term", "habit", "short_memory", "long_memory", "project_rule"]
EntryStatus = Literal["active", "pending", "invalid"]


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
    conditions: list[str] = Field(default_factory=list, max_length=20)
    related_entry_ids: list[str] = Field(default_factory=list, max_length=30)


class UpdateEntry(Schema):
    project_id: SnowflakeId
    version: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    status: EntryStatus | None = None
    kind: EntryKind | None = None
    reason: str = Field(min_length=1, max_length=1000)
    expires_at: datetime | None = None
    conditions: list[str] | None = Field(default=None, max_length=20)
    aliases: list[str] | None = Field(default=None, max_length=20)
    canonical: str | None = Field(default=None, min_length=1, max_length=200)
