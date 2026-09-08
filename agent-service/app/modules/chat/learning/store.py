"""学习草稿及反馈的云端版本日志，任何草稿都不参与正式召回。"""

import asyncio
import copy

from app.core.errors import AppException, ErrorCode
from app.modules.chat.context.store import BlobRef, digest, json_bytes


class DraftStore:
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
                ErrorCode.RESOURCE_CONFLICT, "草稿已进入发布阶段，只能恢复原发布操作"
            )
