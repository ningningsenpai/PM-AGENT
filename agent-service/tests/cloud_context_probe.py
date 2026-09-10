"""显式运行的真实 MinIO 闭环探针；使用隔离前缀和临时 SQLite，不调用模型。"""

from __future__ import annotations

import asyncio
import copy
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocation, get_object_storage
from app.modules.chat.context.fixed_store import FORMAL_FILES, FixedContextStore
from app.modules.chat.context.schemas import UpdateEntry
from app.modules.chat.learning.schemas import ConfirmDraft
from app.modules.chat.learning.service import new_id

from tests.unit.chat.test_persistence import candidate, services


async def main():
    root = f"PM-AGENT/.probes/context-loop-{uuid4().hex}/"
    storage = get_object_storage()
    bucket = get_settings().storage.bucket

    class ProbeFixedStore(FixedContextStore):
        def location(self, user_id, project_id, path):
            if path not in FORMAL_FILES:
                raise AppException(ErrorCode.PARAM_INVALID, "正式上下文目标文件不合法")
            return StorageLocation(
                bucket,
                root + f"{user_id}/{project_id}/system/{path}",
            )

    scope = StorageLocation(bucket, root)
    fixture = services.__wrapped__()
    try:
        async for state in fixture:
            fixed = ProbeFixedStore(storage, bucket)
            state.contexts.storage = storage
            state.contexts.fixed = fixed
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
            assert result["state"] == "applied"
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
            fresh = ProbeFixedStore(storage, bucket)
            snapshots = await fresh.snapshots(1, 11)
            current = next(
                entry
                for snapshot in snapshots.values()
                for entry in snapshot.entries
                if entry["id"] == rule["id"]
            )
            assert current["version"] == 2
            assert current["content"] == "项目代码注释使用简体中文"
            path = current["attributes"]["targetFile"]
            _document, etag = await fresh.read(1, 11, path)
            variants = []
            for name in ("甲", "乙"):
                after = copy.deepcopy(current)
                after["content"] = f"探针并发版本{name}"
                after["version"] += 1
                variants.append(
                    fresh.apply(
                        1,
                        11,
                        path,
                        [
                            {
                                "entryId": current["id"],
                                "before": current,
                                "after": after,
                                "reason": f"探针并发更新{name}",
                                "operationId": f"race:{name}",
                            }
                        ],
                        etag,
                    )
                )
            results = await asyncio.gather(*variants, return_exceptions=True)
            assert sum(not isinstance(item, Exception) for item in results) == 1
            assert any(
                isinstance(item, AppException)
                and item.error == ErrorCode.RESOURCE_CONFLICT
                for item in results
            )
            assert len(await fresh.history(1, 11)) >= 3
            keys = [
                item.object_key
                for item in await asyncio.to_thread(storage.list_prefix, scope)
            ]
            assert not any("/context/" in key for key in keys)
            print(
                "真实 MinIO：MySQL 草稿、固定文件生效、人工纠正、旧确认恢复、独立读取和并发条件写入均通过。"
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
