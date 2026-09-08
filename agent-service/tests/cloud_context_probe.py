"""显式运行的真实 MinIO 闭环探针；使用隔离前缀和临时 SQLite，不调用模型。"""

from __future__ import annotations

import asyncio
import copy
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocation, get_object_storage
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.context.store import ContextStore, VersionCache
from app.modules.chat.learning.schemas import ConfirmDraft
from app.modules.chat.learning.service import new_id
from app.modules.chat.learning.store import DraftStore
from tests.unit.chat.test_persistence import candidate, services


async def main():
    root = f"PM-AGENT/.probes/context-loop-{uuid4().hex}/"
    storage = get_object_storage()
    bucket = get_settings().storage.bucket

    class ProbeStore(ContextStore):
        @staticmethod
        def prefix(user_id, project_id):
            return (
                root + f"{user_id}/{project_id if project_id is not None else 'user'}/"
            )

    scope = StorageLocation(bucket, root)
    fixture = services.__wrapped__()
    try:
        async for state in fixture:
            store = ProbeStore(storage, bucket, VersionCache())
            state.contexts.store = store
            state.learning.drafts = DraftStore(store)
            for pid in (None, 11):
                await store.publish(1, pid, "", [], f"probe-init:{pid}", [])
            output = candidate(
                "请记住，我偏好简洁中文", kind="habit", scope="user", key="表达偏好"
            )
            output.candidates += candidate(
                "项目代码注释使用中文", kind="project_rule", key="代码注释语言"
            ).candidates
            draft = await state.learning.create_draft(
                1,
                11,
                99,
                new_id(),
                output,
                [
                    {
                        "id": "100",
                        "content": "；".join(c.source_quote for c in output.candidates),
                    }
                ],
            )
            assert await state.contexts.list_entries(1, 11) == []
            assert (await state.learning.list(1, 11))[0]["id"] == draft["id"]
            request = ConfirmDraft(
                version=1, candidate_ids=[c["id"] for c in draft["candidates"]]
            )
            result = await state.learning.confirm(1, 11, draft["id"], request)
            assert result["state"] == "published"
            rule = next(
                e
                for e in await state.contexts.list_entries(1, 11)
                if e["kind"] == "project_rule"
            )
            await state.contexts.update_entry(
                1,
                int(rule["id"]),
                UpdateEntry(
                    project_id=11,
                    version=1,
                    content="项目代码注释使用简体中文",
                    reason="探针人工纠正",
                ),
                "probe-edit",
            )
            await state.learning.confirm(1, 11, draft["id"], request)
            fresh = ProbeStore(storage, bucket, VersionCache())
            current = await fresh.load(1, 11)
            assert current.entries[0]["version"] == 2
            assert current.entries[0]["content"] == "项目代码注释使用简体中文"
            variants = []
            for name in ("甲", "乙"):
                entries = copy.deepcopy(current.entries)
                entries[0]["content"] = f"探针并发版本{name}"
                variants.append(
                    fresh.publish(1, 11, current.revision, entries, f"race:{name}", [])
                )
            results = await asyncio.gather(*variants, return_exceptions=True)
            assert sum(not isinstance(item, Exception) for item in results) == 1
            assert any(
                isinstance(item, AppException)
                and item.error == ErrorCode.RESOURCE_CONFLICT
                for item in results
            )
            assert len(await fresh.history(1, 11)) >= 2
            print(
                "真实 MinIO：草稿持久化、双范围发布、人工纠正、旧确认恢复、独立缓存读取、并发条件写入均通过。"
            )
            break
    finally:
        await fixture.aclose()
        # 仅清理本进程创建的随机探针前缀，不接触用户和项目对象。
        if not root.startswith("PM-AGENT/.probes/context-loop-") or not root.endswith(
            "/"
        ):
            raise RuntimeError("探针清理范围不合法")
        await asyncio.to_thread(storage.remove_prefix, scope)
        assert not await asyncio.to_thread(storage.list_prefix, scope)
        print("探针对象已清理。")


if __name__ == "__main__":
    asyncio.run(main())
