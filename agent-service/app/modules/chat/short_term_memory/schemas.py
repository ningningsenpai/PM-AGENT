"""短期记忆空文件结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.identifiers import SnowflakeId

# 当前仅保留空文件顶层结构；条目模型及内容生成、更新规则均处于冻结状态，
# 后续测试使用的短期记忆文件由测试人员直接上传至 MinIO。


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
