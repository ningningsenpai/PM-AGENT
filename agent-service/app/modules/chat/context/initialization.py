"""Chat 项目上下文空文件初始化。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.infrastructure.storage import ObjectStorage, StorageLocationFactory

from .documents.long_term_memory import LongTermMemoryDocument
from .documents.short_term_memory import ShortTermMemoryDocument
from .documents.user_habits import UserHabitCategory, UserHabitsDocument

# 初始化仅创建缺失的空文件；显式学习的权威条目与版本快照由上下文服务管理。


class ChatContextInitializationService:
    """为新项目创建 Chat 上下文所需的空文件。"""

    _HABIT_CATEGORIES: tuple[UserHabitCategory, ...] = (
        "work",
        "thinking",
        "specification",
        "tooling",
        "life",
    )

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._storage = storage
        self._locations = locations

    async def initialize(self, project: Any) -> None:
        """幂等创建长短期记忆、用户习惯和更新日志空文件。"""
        initialized_at = datetime.now()
        documents: list[tuple[str, BaseModel]] = [
            (
                "short_term_memory.json",
                ShortTermMemoryDocument(
                    project_id=project.id,
                    updated_at=initialized_at,
                ),
            ),
            (
                "long_term_memory.json",
                LongTermMemoryDocument(
                    project_id=project.id,
                    updated_at=initialized_at,
                ),
            ),
            *[
                (
                    f"user_habits/{category}.json",
                    UserHabitsDocument(
                        project_id=project.id,
                        category=category,
                        updated_at=initialized_at,
                    ),
                )
                for category in self._HABIT_CATEGORIES
            ],
        ]
        for relative_path, document in documents:
            await self._create_if_absent(
                project,
                relative_path,
                json.dumps(
                    document.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
                "application/json",
            )
        await self._create_if_absent(
            project,
            "update_journal.jsonl",
            b"",
            "application/x-ndjson",
        )

    async def _create_if_absent(
        self,
        project: Any,
        relative_path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        location = self._locations.system_file(
            project.owner_user_id,
            project.id,
            relative_path,
        )
        if await asyncio.to_thread(self._storage.exists, location):
            return
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            content,
            content_type,
        )
