"""云端上下文读取、一次性迁移及人工纠正；数据库仅保留过程记录。"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.modules.chat.context.models import AgentContextScope
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from .conflicts import conflicts, validate_conflicts
from .migration import legacy_cloud, specification_entries
from .schemas import EntryView
from .serialization import entry_data, utc_naive
from .store import ContextStore, digest, json_bytes


class ContextService:
    def __init__(self, repository, projects, storage, bucket):
        self.repo, self.projects, self.storage, self.bucket = (
            repository,
            projects,
            storage,
            bucket,
        )
        self.store = ContextStore(storage, bucket)

    async def authorize(self, user_id, project_id):
        await self.projects.get_owned(user_id, project_id)

    @staticmethod
    def key(user_id, project_id):
        return f"{user_id}:{project_id if project_id is not None else 'user'}"

    async def scopes(self, user_id, project_id, *, lock=False):
        result = []
        # 范围记录按用户、项目固定顺序加锁，协调会话自动编号。
        for pid in (None, project_id):
            key = self.key(user_id, pid)
            scope = await self.repo.scope(key, lock=lock)
            if scope is None:
                try:
                    async with self.repo.session.begin_nested():
                        scope = await self.repo.add(
                            AgentContextScope(
                                scope_key=key,
                                user_id=user_id,
                                project_id=pid,
                                version=0,
                                published_version=0,
                            )
                        )
                except IntegrityError:
                    scope = await self.repo.scope(key, lock=lock)
            result.append(scope)
        return result

    async def release_reads(self):
        if self.repo.session.in_transaction():
            await self.repo.session.rollback()

    async def snapshots(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        await self.repo.session.commit()
        result = {}
        for pid in (None, project_id):
            snapshot = await self.store.load(user_id, pid)
            if snapshot.manifest is None:
                snapshot = await self._migrate(user_id, pid)
            result[self.key(user_id, pid)] = snapshot
        return result

    async def _migrate(self, user_id, project_id):
        prefix = self.store.prefix(user_id, project_id)
        if await self.store._read(
            self.store.location(prefix, "migration-complete.json")
        ):
            raise AppException(
                ErrorCode.FILE_STORAGE_ERROR,
                "云端版本清单丢失，请恢复清单，不能退回旧数据库内容",
            )
        rows = await self.repo.entries(user_id, project_id, effective=False)
        entries = [entry_data(row) for row in rows if row.project_id == project_id]
        changes = await self.repo.changes(
            [int(entry["id"]) for entry in entries], limit=None
        )
        history = [
            {
                "id": str(row.id),
                "entryId": str(row.entry_id),
                "version": row.version,
                "before": row.before,
                "after": row.after,
                "reason": row.reason,
                "sourceMessageId": str(row.source_message_id)
                if row.source_message_id
                else None,
            }
            for row in changes
        ]
        await self.repo.session.commit()
        cloud, old_history, specification = await legacy_cloud(
            self.store, user_id, project_id
        )
        entries.extend(cloud)
        try:
            await self.store.publish(
                user_id,
                project_id,
                "",
                entries,
                f"migration-v2:{user_id}:{project_id}",
                history + old_history,
                specification=specification,
            )
        except AppException as exc:
            snapshot = await self.store.load(user_id, project_id)
            if exc.error != ErrorCode.RESOURCE_CONFLICT or snapshot.manifest is None:
                raise
        await self.store.immutable(
            prefix, "migration-complete.json", json_bytes({"version": 2})
        )
        return await self.store.load(user_id, project_id)

    @staticmethod
    def effective(entry):
        expires = entry.get("expiresAt")
        deadline = (
            utc_naive(datetime.fromisoformat(expires.replace("Z", "+00:00")))
            if expires
            else None
        )
        return entry["status"] == "active" and (
            deadline is None or deadline > datetime.now(UTC).replace(tzinfo=None)
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
        return {
            key: snapshot.version
            for key, snapshot in (await self.snapshots(user_id, project_id)).items()
        }

    async def changes(self, user_id, project_id, entry_id=None):
        snapshots = await self.snapshots(user_id, project_id)
        if entry_id is not None and not any(
            str(entry_id) == e["id"] for s in snapshots.values() for e in s.entries
        ):
            raise AppException(ErrorCode.FORBIDDEN, "条目不属于当前上下文范围")
        result = []
        for pid in (None, project_id):
            result.extend(await self.store.history(user_id, pid))
        return [
            change
            for change in result
            if entry_id is None or change.get("entryId") == str(entry_id)
        ]

    async def update_entry(self, user_id, entry_id, request, key=None):
        if not key or len(key) > 128:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        snapshots = await self.snapshots(user_id, request.project_id)
        all_entries = [e for s in snapshots.values() for e in s.entries]
        row = next((e for e in all_entries if e["id"] == str(entry_id)), None)
        if row is None:
            raise AppException(ErrorCode.FORBIDDEN, "内容条目不存在或无权访问")
        pid = int(row["projectId"]) if row["projectId"] else None
        snapshot = snapshots[self.key(user_id, pid)]
        operation = f"edit:{user_id}:{key}"
        prefix = self.store.prefix(user_id, pid)
        path = "edits/" + digest(operation.encode()) + ".json"
        fingerprint = digest(
            json_bytes(
                {"entryId": str(entry_id), "request": request.model_dump(mode="json")}
            )
        )
        saved = await self.store._read(self.store.location(prefix, path))
        if saved:
            plan = json.loads(saved[0])
            if plan["requestHash"] != fingerprint:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同纠正内容"
                )
        else:
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
            if request.kind is not None and request.kind != row["kind"]:
                if row["kind"] != "short_memory" or request.kind != "long_memory":
                    raise AppException(
                        ErrorCode.PARAM_INVALID, "仅支持将短期记忆晋升为长期记忆"
                    )
                after["kind"], after["expiresAt"] = request.kind, None
            if "expires_at" in request.model_fields_set:
                after["expiresAt"] = (
                    request.expires_at.isoformat() if request.expires_at else None
                )
            if request.aliases is not None or request.canonical is not None:
                if row["kind"] != "term":
                    raise AppException(
                        ErrorCode.PARAM_INVALID, "仅词条支持别名和标准词"
                    )
                after["attributes"].update(
                    {
                        k: v
                        for k, v in {
                            "aliases": request.aliases,
                            "canonical": request.canonical,
                        }.items()
                        if v is not None
                    }
                )
            if row["kind"] == "term" and not (
                after["attributes"].get("aliases")
                and after["attributes"].get("canonical")
            ):
                raise AppException(ErrorCode.PARAM_INVALID, "词条必须包含标准词和别名")
            after["attributes"]["humanEdited"] = True
            after["version"] += 1
            after = EntryView.model_validate(after).model_dump(
                mode="json", by_alias=True
            )
            validate_conflicts(
                [after if e["id"] == row["id"] else e for e in all_entries], {row["id"]}
            )
            plan = {
                "requestHash": fingerprint,
                "base": snapshot.revision,
                "entries": [
                    after if e["id"] == row["id"] else e for e in snapshot.entries
                ],
                "after": after,
                "changes": [
                    {
                        "entryId": row["id"],
                        "version": after["version"],
                        "before": row,
                        "after": after,
                        "reason": sanitize_sensitive_content(request.reason).text,
                        "sourceMessageId": None,
                    }
                ],
            }
            await self.store.immutable(prefix, path, json_bytes(plan))
        receipt = await self.store.publish(
            user_id, pid, plan["base"], plan["entries"], operation, plan["changes"]
        )
        return {
            **plan["after"],
            "publication": {
                "version": receipt.version,
                "revision": receipt.revision,
                "published": True,
            },
        }

    async def publish(self, user_id, project_id):
        # 兼容旧客户端的重试入口：只读取正式版本，不从旧数据库重新生成正文。
        return {
            key: {"version": snapshot.version, "published": True, "error": None}
            for key, snapshot in (await self.snapshots(user_id, project_id)).items()
        }

    async def specification_snapshot(self, user_id, project_id):
        snapshot = (await self.snapshots(user_id, project_id))[
            self.key(user_id, project_id)
        ]
        document = None
        if snapshot.manifest.specification:
            document = await self.store.blob(
                self.store.prefix(user_id, project_id), snapshot.manifest.specification
            )
        return snapshot, document

    async def publish_specification(self, user_id, project_id, snapshot, document):
        entries = copy.deepcopy(snapshot.entries)
        by_id = {e["id"]: e for e in entries}
        changes = []
        for proposed in specification_entries(project_id, document):
            before = by_id.get(proposed["id"])
            # 人工确认过的条目由用户维护，文件刷新不能悄悄覆盖。
            if before and before["attributes"].get("humanEdited"):
                if before["content"] != proposed["content"]:
                    changes.append(
                        {
                            "entryId": before["id"],
                            "reason": "文件候选与人工纠正不同，保留人工版本",
                            "proposal": proposed,
                        }
                    )
                continue
            if any(conflicts(proposed, e) for e in entries):
                proposed["status"] = "pending"
            proposed["version"] = before["version"] if before else 1
            if before == proposed:
                continue
            if before:
                proposed["version"] += 1
                entries[entries.index(before)] = proposed
            else:
                entries.append(proposed)
            changes.append(
                {
                    "entryId": proposed["id"],
                    "version": proposed["version"],
                    "before": before or {},
                    "after": proposed,
                    "reason": "项目文件解析刷新规范",
                }
            )
        operation = "specification:" + digest(
            json_bytes({"base": snapshot.revision, "document": document})
        )
        return await self.store.publish(
            user_id,
            project_id,
            snapshot.revision,
            entries,
            operation,
            changes,
            specification=document,
        )
