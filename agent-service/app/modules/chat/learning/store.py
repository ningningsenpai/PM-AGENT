"""显式学习草稿的 MySQL 存储，以及旧 MinIO 草稿的只读迁移入口。"""

import asyncio
import copy

from app.core.errors import AppException, ErrorCode
from app.modules.chat.context.store import BlobRef, digest, json_bytes

from .models import AgentLearningDraft


class DraftStore:
    """将完整草稿负载存入 MySQL，并用独立锁版本保护并发修改。"""

    def __init__(self, repository):
        self.repository = repository

    async def load(self, user_id, project_id, draft_id):
        if not str(draft_id).isdigit():
            raise AppException(ErrorCode.PARAM_INVALID, "草稿编号不合法")
        row = await self.repository.get(user_id, project_id, int(draft_id))
        if row is None:
            raise AppException(ErrorCode.PARAM_INVALID, "学习草稿不存在或无权访问")
        return copy.deepcopy(row.payload), row.lock_version

    async def save(self, data, lock_version):
        user_id = int(data["userId"])
        project_id = int(data["projectId"])
        draft_id = int(data["id"])
        if lock_version is None:
            if await self.repository.get(user_id, project_id, draft_id) is not None:
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "学习草稿已经存在")
            row = AgentLearningDraft(
                id=draft_id,
                user_id=user_id,
                project_id=project_id,
                conversation_id=int(data["conversationId"]),
                version=int(data["version"]),
                lock_version=1,
                state=data["state"],
                payload=copy.deepcopy(data),
            )
            await self.repository.add(row)
        else:
            row = await self.repository.get(user_id, project_id, draft_id, lock=True)
            if row is None:
                raise AppException(ErrorCode.PARAM_INVALID, "学习草稿不存在或无权访问")
            if row.lock_version != int(lock_version):
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "草稿已被其他操作修改，请刷新"
                )
            row.version = int(data["version"])
            row.state = data["state"]
            row.payload = copy.deepcopy(data)
            row.lock_version += 1
        await self.repository.session.commit()
        return copy.deepcopy(data)

    async def list(self, user_id, project_id, conversation_id=None):
        rows = await self.repository.list(user_id, project_id, conversation_id)
        return [copy.deepcopy(row.payload) for row in rows]

    @staticmethod
    def next_version(data, reason):
        result = copy.deepcopy(data)
        result.setdefault("history", []).append(
            {
                "version": data["version"],
                "candidates": data["candidates"],
                "reason": reason,
            }
        )
        result["version"] += 1
        return result

    @staticmethod
    def editable(data, version):
        if data["version"] != version:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "草稿版本已变化，请重新查看"
            )
        if data.get("plan") is not None:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "草稿已进入更新阶段，只能恢复原确认操作"
            )


class LegacyDraftStore:
    """仅供一次性迁移读取旧 Context 目录中的草稿。"""

    def __init__(self, contexts):
        self.contexts = contexts

    def prefix(self, user_id, project_id, draft_id):
        if not str(draft_id).isdigit():
            raise AppException(ErrorCode.PARAM_INVALID, "草稿编号不合法")
        return self.contexts.prefix(user_id, project_id) + f"drafts/{draft_id}/"

    async def load(self, user_id, project_id, draft_id):
        prefix = self.prefix(user_id, project_id, draft_id)
        pointer = await self.contexts._read(
            self.contexts.location(prefix, "manifest.json")
        )
        if pointer is None:
            raise AppException(ErrorCode.PARAM_INVALID, "学习草稿不存在或无权访问")
        data = await self.contexts.blob(prefix, BlobRef.model_validate_json(pointer[0]))
        if (data["userId"], data["projectId"], data["id"]) != (
            str(user_id),
            str(project_id),
            str(draft_id),
        ):
            raise AppException(ErrorCode.FORBIDDEN, "学习草稿所属范围不一致")
        return data, pointer[1]

    async def save(self, data, etag):
        prefix = self.prefix(data["userId"], data["projectId"], data["id"])
        content = json_bytes(data)
        ref = await self.contexts.immutable(
            prefix, f"revisions/{digest(content)}.json", content
        )
        try:
            await asyncio.to_thread(
                self.contexts.storage.compare_and_put,
                self.contexts.location(prefix, "manifest.json"),
                json_bytes(ref.model_dump()),
                etag,
            )
        except AppException:
            latest, _ = await self.load(data["userId"], data["projectId"], data["id"])
            if latest != data:
                raise
        return data

    async def list(self, user_id, project_id, conversation_id=None):
        prefix = self.contexts.prefix(user_id, project_id) + "drafts/"
        objects = await asyncio.to_thread(
            self.contexts.storage.list_prefix, self.contexts.location(prefix, "")
        )
        result = []
        for item in objects:
            name = item if isinstance(item, str) else item.object_key
            relative = name.removeprefix(prefix).split("/")
            if len(relative) != 2 or relative[1] != "manifest.json":
                continue
            draft, _ = await self.load(user_id, project_id, relative[0])
            if conversation_id is None or draft["conversationId"] == str(
                conversation_id
            ):
                result.append(draft)
        return sorted(result, key=lambda d: int(d["id"]), reverse=True)
