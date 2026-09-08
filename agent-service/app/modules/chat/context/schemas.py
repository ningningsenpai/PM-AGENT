"""学习上下文的类型、查询与纠正契约。"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema

EntryKind = Literal["term", "habit", "short_memory", "long_memory"]
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


class UpdateEntry(Schema):
    version: int = Field(ge=1)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    status: EntryStatus | None = None
    kind: EntryKind | None = None
    reason: str = Field(min_length=1, max_length=1000)
    expires_at: datetime | None = None
