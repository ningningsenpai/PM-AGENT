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
