"""固定上下文文件的查询、条件更新与兼容接口。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from datetime import datetime

from app.core.errors import AppException, ErrorCode
from app.core.time import as_shanghai, shanghai_iso, shanghai_now
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content
from app.project_context.specification.schemas import (
    ProjectSpecificationDocument,
    merge_specifications,
)

from .conflicts import validate_conflicts
from .fixed_store import PROJECT_SPECIFICATION, FixedContextSnapshot, FixedContextStore
from .schemas import EntryView
from .store import ContextStore


class ContextService:
    """以 system 固定文件为唯一正式来源；旧 ContextStore 仅供迁移读取。"""

    def __init__(self, repository, projects, storage, bucket):
        self.repo = repository
        self.projects = projects
        self.storage = storage
        self.bucket = bucket
        self.fixed = FixedContextStore(storage, bucket)
        self.legacy_store = ContextStore(storage, bucket)

    async def authorize(self, user_id, project_id):
        await self.projects.get_owned(user_id, project_id)

    @staticmethod
    def key(user_id, project_id):
        return f"{user_id}:{project_id if project_id is not None else 'user'}"

    async def release_reads(self):
        if self.repo.session.in_transaction():
            await self.repo.session.rollback()

    async def snapshots(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        await self.repo.session.commit()
        return await self.fixed.snapshots(user_id, project_id)

    async def file_versions(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        await self.repo.session.commit()
        return await self.fixed.versions(user_id, project_id)

    @staticmethod
    def effective(entry):
        expires = entry.get("expiresAt")
        deadline = (
            as_shanghai(datetime.fromisoformat(expires.replace("Z", "+00:00")))
            if expires
            else None
        )
        return entry["status"] == "active" and (
            deadline is None or deadline > shanghai_now()
        )

    async def list_entries(
        self, user_id, project_id, *, effective=True, kind=None, query=None
    ):
        snapshots = await self.snapshots(user_id, project_id)
        result = [
            copy.deepcopy(entry)
            for snapshot in snapshots.values()
            for entry in snapshot.entries
            if (not effective or self.effective(entry))
            and (kind is None or entry["kind"] == kind)
        ]
        if query:
            words = set(query.lower())
            result.sort(
                key=lambda item: len(words & set(item["content"].lower())), reverse=True
            )
        return result

    async def versions(self, user_id, project_id):
        return await self.file_versions(user_id, project_id)

    async def changes(self, user_id, project_id, entry_id=None):
        await self.authorize(user_id, project_id)
        entries = await self.list_entries(user_id, project_id, effective=False)
        if entry_id is not None and not any(
            str(entry_id) == entry["id"] for entry in entries
        ):
            raise AppException(ErrorCode.FORBIDDEN, "条目不属于当前上下文范围")
        result = await self.fixed.history(user_id, project_id)
        return [
            change
            for change in result
            if entry_id is None or change.get("entryId") == str(entry_id)
        ]

    async def update_entry(self, user_id, entry_id, request, key=None):
        key = (key or "").strip()
        if not key or len(key) > 128:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        await self.authorize(user_id, request.project_id)
        request_hash = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        operation_id = f"manual:{user_id}:{entry_id}:{key}"
        history = await self.fixed.history(user_id, request.project_id)
        for historical in history:
            if historical.get("operationId") != operation_id:
                continue
            if historical.get("requestHash") != request_hash:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同的纠正内容"
                )
            versions = await self.file_versions(user_id, request.project_id)
            target = self.fixed.target_for(historical["after"])
            return {
                **historical["after"],
                "publication": {
                    "version": historical["after"]["version"],
                    "revision": versions.get(target) or "",
                    "published": True,
                },
            }
        staged = next(
            (
                historical
                for historical in history
                if historical.get("operationId") == f"{operation_id}:stage"
            ),
            None,
        )
        if staged is not None:
            if staged.get("requestHash") != request_hash:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同的纠正内容"
                )
            row = staged["before"]
            after = staged["after"]
            old_target = self.fixed.target_for(row)
            target = self.fixed.target_for(after)
            versions = await self.file_versions(user_id, request.project_id)
            removal = {
                "entryId": row["id"],
                "before": row,
                "after": after,
                "version": after["version"],
                "reason": staged.get("reason") or "用户晋升记忆",
                "sourceMessageId": None,
                "operationId": operation_id,
                "requestHash": request_hash,
                "delete": True,
            }
            await self.fixed.apply(
                user_id,
                request.project_id,
                old_target,
                [removal],
                versions[old_target],
            )
            return {
                **after,
                "publication": {
                    "version": after["version"],
                    "revision": versions.get(target) or "",
                    "published": True,
                },
            }
        entries = await self.list_entries(user_id, request.project_id, effective=False)
        row = next((entry for entry in entries if entry["id"] == str(entry_id)), None)
        if row is None:
            raise AppException(ErrorCode.FORBIDDEN, "内容条目不存在或无权访问")
        if row["version"] != request.version:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "条目版本已变化，请重新读取"
            )
        after = copy.deepcopy(row)
        for field in ("content", "status", "conditions"):
            value = getattr(request, field)
            if value is not None:
                after[field] = (
                    sanitize_sensitive_content(value).text
                    if field == "content"
                    else value
                )
        if "expires_at" in request.model_fields_set:
            after["expiresAt"] = (
                shanghai_iso(request.expires_at) if request.expires_at else None
            )
        old_target = self.fixed.target_for(row)
        if request.kind is not None and request.kind != row["kind"]:
            if row["kind"] != "short_memory" or request.kind != "long_memory":
                raise AppException(
                    ErrorCode.PARAM_INVALID, "仅支持将短期记忆晋升为长期记忆"
                )
            after["kind"] = request.kind
            after["expiresAt"] = None
            after["attributes"]["targetFile"] = "long_term_memory.json"
        if request.aliases is not None or request.canonical is not None:
            if row["kind"] != "term":
                raise AppException(ErrorCode.PARAM_INVALID, "仅词条支持别名和标准词")
            after["attributes"].update(
                {
                    name: value
                    for name, value in {
                        "aliases": request.aliases,
                        "canonical": request.canonical,
                    }.items()
                    if value is not None
                }
            )
        after["attributes"]["humanEdited"] = True
        after["version"] += 1
        after = EntryView.model_validate(after).model_dump(mode="json", by_alias=True)
        validate_conflicts(
            [after if entry["id"] == row["id"] else entry for entry in entries],
            {row["id"]},
        )
        versions = await self.file_versions(user_id, request.project_id)
        reason = sanitize_sensitive_content(request.reason).text
        target = self.fixed.target_for(after)
        if target != old_target:
            staged_change = {
                "entryId": row["id"],
                "before": row,
                "after": after,
                "version": after["version"],
                "reason": reason,
                "sourceMessageId": None,
                "operationId": f"{operation_id}:stage",
                "requestHash": request_hash,
            }
            receipt = await self.fixed.apply(
                user_id,
                request.project_id,
                target,
                [staged_change],
                versions[target],
            )
            removal = {
                "entryId": row["id"],
                "before": row,
                "after": after,
                "version": after["version"],
                "reason": reason,
                "sourceMessageId": None,
                "operationId": operation_id,
                "requestHash": request_hash,
                "delete": True,
            }
            await self.fixed.apply(
                user_id, request.project_id, old_target, [removal], versions[old_target]
            )
        else:
            change = {
                "entryId": row["id"],
                "before": row,
                "after": after,
                "version": after["version"],
                "reason": reason,
                "sourceMessageId": None,
                "operationId": operation_id,
                "requestHash": request_hash,
            }
            receipt = await self.fixed.apply(
                user_id, request.project_id, target, [change], versions[target]
            )
        return {
            **after,
            "publication": {
                "version": receipt.version,
                "revision": receipt.revision,
                "published": True,
            },
        }

    async def publish(self, user_id, project_id):
        """兼容旧发布入口：只返回固定文件状态，不创建 Context 版本。"""
        versions = await self.file_versions(user_id, project_id)
        return {
            path: {
                "version": 1,
                "revision": etag,
                "published": etag is not None,
                "error": None,
            }
            for path, etag in versions.items()
        }

    async def specification_snapshot(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        await self.repo.session.commit()
        document, etag = await self.fixed.read(
            user_id, project_id, PROJECT_SPECIFICATION
        )
        return FixedContextSnapshot(
            etag or "", [], {PROJECT_SPECIFICATION: etag}, etag
        ), document

    async def publish_specification(self, user_id, project_id, snapshot, document):
        """兼容规范服务的条件写入；新解析服务直接使用固定文件。"""
        parsed = ProjectSpecificationDocument.model_validate(document)
        if int(parsed.project_id) != int(project_id):
            raise AppException(ErrorCode.FORBIDDEN, "项目规范所属项目不一致")
        current, etag = await self.fixed.read(
            user_id, project_id, PROJECT_SPECIFICATION
        )
        if etag != snapshot.etag:
            raise AppException(ErrorCode.RESOURCE_CONFLICT, "项目规范基础版本已变化")
        merged = merge_specifications(
            ProjectSpecificationDocument.model_validate(current), parsed
        )
        body = json.dumps(
            merged.model_dump(mode="json"), ensure_ascii=False, indent=2
        ).encode()
        revision = await asyncio.to_thread(
            self.storage.compare_and_put,
            self.fixed.location(user_id, project_id, PROJECT_SPECIFICATION),
            body,
            etag,
        )
        return {"version": 1, "revision": revision, "published": True}
