"""Chat 项目上下文空文件初始化。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from typing import Any

from pydantic import BaseModel

from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.modules.chat.long_term_memory import LongTermMemoryDocument
from app.modules.chat.short_term_memory import ShortTermMemoryDocument
from app.modules.chat.user_habits import UserHabitCategory, UserHabitsDocument

# 业务冻结说明：当前仅保留项目初始化时的空白占位文件创建，不实现用户习惯、
# 长短期记忆和更新日志的内容构建。后续测试由测试人员直接向 MinIO 上传对应
# 文件，作为用户输入信息提取的既有上下文；正式解冻前不得扩展生成、合并、
# 晋升、更新或召回链路。


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
