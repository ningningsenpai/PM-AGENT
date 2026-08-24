"""用户习惯空文件结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

UserHabitCategory = Literal[
    "work",
    "thinking",
    "specification",
    "tooling",
    "life",
]

# 当前仅保留分类空文件的顶层结构；习惯条目模型及内容生成、更新规则均处于
# 冻结状态，后续测试使用的用户习惯文件由测试人员直接上传至 MinIO。


class UserHabitsDocument(BaseModel):
    """项目单类用户习惯文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid")

    project_id: int
    schema_version: str = "1.0.0"
    category: UserHabitCategory
    updated_at: datetime
    user_habits: list[dict[str, Any]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    ignored_items: list[dict[str, Any]] = Field(default_factory=list)
