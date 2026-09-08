"""短期记忆空文件结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.identifiers import SnowflakeId

# 保留初始化文件的既有格式；学习条目使用 context/schemas.py 中的独立契约。


class ShortTermMemoryDocument(BaseModel):
    """项目短期记忆文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid")

    project_id: SnowflakeId
    schema_version: str = "1.0.0"
    updated_at: datetime
    short_term_memory: list[dict[str, Any]] = Field(default_factory=list)
    promotion_candidates: list[dict[str, Any]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    ignored_items: list[dict[str, Any]] = Field(default_factory=list)
