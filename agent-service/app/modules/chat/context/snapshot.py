"""发布不可变版本快照；存储失败保留已经提交的学习结果。"""

import asyncio
import json
import logging

from app.infrastructure.storage import StorageLocation

from .serialization import entry_data


class ContextSnapshotPublisher:
    def __init__(self, repository, storage, bucket):
        self.repo, self.storage, self.bucket = repository, storage, bucket

    async def publish_scope(self, key):
        scope = await self.repo.scope(key)
        version = scope.version
        entries = await self.repo.entries(
            scope.user_id, scope.project_id, effective=False
        )
        document = {
            "scopeKey": key,
            "version": version,
            "entries": [entry_data(row) for row in entries if row.scope_key == key],
        }
        # 快照文件按版本不可变；失败不会回滚已提交的学习结果。
        prefix = (
            f"PM-AGENT/{scope.user_id}/{scope.project_id}/system/learned_context"
            if scope.project_id
            else f"PM-AGENT/user_context/{scope.user_id}"
        )
        location = StorageLocation(self.bucket, f"{prefix}/v{version}.json")
        await self.repo.session.commit()
        error = None
        try:
            await asyncio.to_thread(
                self.storage.put_bytes,
                location,
                json.dumps(document, ensure_ascii=False).encode(),
                "application/json",
            )
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "上下文业务运行失败，保留当前调用记录"
            )
            error = f"快照发布失败：{type(exc).__name__}"
        current = await self.repo.scope(key, lock=True)
        if error is None:
            current.published_version = max(current.published_version, version)
        current.snapshot_error = error
        await self.repo.session.commit()
        return {"version": version, "published": error is None, "error": error}
