"""长期记忆空文件结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LongTermMemoryDocument(BaseModel):
    """项目长期记忆文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid")

    project_id: int
    schema_version: str = "1.0.0"
    updated_at: datetime
    long_term_memory: list[dict[str, Any]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    ignored_items: list[dict[str, Any]] = Field(default_factory=list)
