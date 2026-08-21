"""Chat 项目上下文初始化测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from app.core.config import StorageConfig
from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.modules.chat import ChatContextInitializationService


class RecordingStorage:
    """记录测试期间对象存储的写入结果。"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.put_calls: list[str] = []

    def exists(self, location: StorageLocation) -> bool:
        return location.object_key in self.objects

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        content_type: str,
    ) -> None:
        self.objects[location.object_key] = content
        self.content_types[location.object_key] = content_type
        self.put_calls.append(location.object_key)


def _locations() -> StorageLocationFactory:
    return StorageLocationFactory(
        StorageConfig(
            endpoint="127.0.0.1:9000",
            access_key="test",
            secret_key="test",
            secure=False,
            bucket="pm-agent-test",
            read_url_expiry_seconds=300,
        )
    )


def _project():
    return SimpleNamespace(id=12, owner_user_id=7)


class ChatContextInitializationServiceTest(IsolatedAsyncioTestCase):
    async def test_initialize_creates_all_empty_context_files(self) -> None:
        """验证初始化按固定路径创建七个 JSON 和一个 JSONL 文件。"""
        storage = RecordingStorage()
        service = ChatContextInitializationService(storage, _locations())

        await service.initialize(_project())

        expected_paths = [
            "short_term_memory.json",
            "long_term_memory.json",
            "user_habits/work.json",
            "user_habits/thinking.json",
            "user_habits/specification.json",
            "user_habits/tooling.json",
            "user_habits/life.json",
            "update_journal.jsonl",
        ]
        expected_keys = [f"PM-AGENT/7/12/system/{path}" for path in expected_paths]
        self.assertEqual(expected_keys, storage.put_calls)

        json_documents = [
            json.loads(storage.objects[key]) for key in expected_keys[:-1]
        ]
        self.assertTrue(
            all(document["project_id"] == 12 for document in json_documents)
        )
        self.assertTrue(
            all(document["schema_version"] == "1.0.0" for document in json_documents)
        )
        self.assertEqual(
            1,
            len({document["updated_at"] for document in json_documents}),
        )
        self.assertEqual([], json_documents[0]["short_term_memory"])
        self.assertEqual([], json_documents[0]["promotion_candidates"])
        self.assertEqual([], json_documents[1]["long_term_memory"])
        self.assertEqual(
            ["work", "thinking", "specification", "tooling", "life"],
            [document["category"] for document in json_documents[2:]],
        )
        self.assertTrue(
            all(document["user_habits"] == [] for document in json_documents[2:])
        )
        self.assertTrue(all(document["changes"] == [] for document in json_documents))
        self.assertTrue(
            all(document["ignored_items"] == [] for document in json_documents)
        )
        self.assertEqual(b"", storage.objects[expected_keys[-1]])
        self.assertEqual(
            "application/x-ndjson",
            storage.content_types[expected_keys[-1]],
        )
        self.assertTrue(
            all(
                storage.content_types[key] == "application/json"
                for key in expected_keys[:-1]
            )
        )

    async def test_initialize_keeps_existing_objects(self) -> None:
        """验证重复初始化不会覆盖已经存在的上下文对象。"""
        storage = RecordingStorage()
        service = ChatContextInitializationService(storage, _locations())
        project = _project()
        await service.initialize(project)
        existing_key = "PM-AGENT/7/12/system/short_term_memory.json"
        storage.objects[existing_key] = b"existing"
        storage.put_calls.clear()

        await service.initialize(project)

        self.assertEqual(b"existing", storage.objects[existing_key])
        self.assertEqual([], storage.put_calls)
