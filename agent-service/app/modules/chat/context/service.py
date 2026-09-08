"""MySQL 权威上下文、显式纠正和可重试的版本快照。"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import get_snowflake_id_generator
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from ..models import AgentContextChange, AgentContextScope
from .serialization import entry_data, utc_naive
from .snapshot import ContextSnapshotPublisher


class ContextService:
    def __init__(self, repository, projects, storage, bucket):
        self.repo = repository
        self.projects = projects
        self.storage = storage
        self.bucket = bucket

    async def authorize(self, user_id, project_id):
        await self.projects.get_owned(user_id, project_id)

    @staticmethod
    def key(user_id, project_id):
        return f"{user_id}:{project_id if project_id is not None else 'user'}"

    async def scopes(self, user_id, project_id, *, lock=False):
        result = []
        # 用户范围先于项目范围加锁，避免两个项目同时学习时锁顺序交错。
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
        """只读工具结束后释放共享请求中的读事务，再进入下一次模型调用。"""
        if self.repo.session.in_transaction():
            await self.repo.session.rollback()

    async def list_entries(
        self, user_id, project_id, *, effective=True, kind=None, query=None
    ):
        await self.authorize(user_id, project_id)
        entries = await self.repo.entries(user_id, project_id, effective=effective)
        result = [
            entry_data(row) for row in entries if kind is None or row.kind == kind
        ]
        await self.repo.session.commit()
        if query:
            words = set(query.lower())
            result.sort(
                key=lambda item: len(words & set(item["content"].lower())), reverse=True
            )
        return result

    async def versions(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        scopes = await self.scopes(user_id, project_id)
        result = {scope.scope_key: scope.version for scope in scopes}
        await self.repo.session.commit()
        return result

    async def update_entry(self, user_id, entry_id, request):
        row = await self.repo.entry(user_id, entry_id)
        if row is None:
            raise AppException(ErrorCode.PARAM_INVALID, "内容条目不存在或无权访问")
        if row.project_id is not None:
            await self.authorize(user_id, row.project_id)
        scope = await self.repo.scope(row.scope_key, lock=True)
        row = await self.repo.entry(user_id, entry_id, lock=True)
        if row.version != request.version:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "条目版本已变化，请重新读取"
            )
        before = entry_data(row)
        if request.content is not None:
            if row.kind == "term":
                raise AppException(
                    ErrorCode.PARAM_INVALID,
                    "词条映射请通过对话纠正后显式 learn，避免描述与别名映射不一致",
                )
            row.content = sanitize_sensitive_content(request.content).text
        if request.status is not None:
            row.status = request.status
        if request.kind is not None:
            if row.kind != "short_memory" or request.kind != "long_memory":
                raise AppException(
                    ErrorCode.PARAM_INVALID, "仅支持将短期记忆显式晋升为长期记忆"
                )
            row.kind = "long_memory"
            row.expires_at = None
        if "expires_at" in request.model_fields_set:
            row.expires_at = utc_naive(request.expires_at)
        row.version += 1
        scope.version += 1
        await self.add_change(row, before, request.reason, None)
        result = entry_data(row)
        await self.repo.session.commit()
        result["snapshot"] = await self.publish_scope(scope.scope_key)
        return result

    async def add_change(self, row, before, reason, message_id):
        await self.repo.add(
            AgentContextChange(
                id=get_snowflake_id_generator().next_id(),
                entry_id=row.id,
                version=row.version,
                before=before,
                after=entry_data(row),
                reason=sanitize_sensitive_content(reason).text,
                source_message_id=message_id,
            )
        )

    async def changes(self, user_id, project_id, entry_id=None):
        await self.authorize(user_id, project_id)
        entries = await self.repo.entries(user_id, project_id, effective=False)
        ids = [row.id for row in entries if entry_id is None or row.id == entry_id]
        if entry_id and not ids:
            raise AppException(ErrorCode.FORBIDDEN, "条目不属于当前上下文范围")
        rows = await self.repo.changes(ids)
        result = [
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
            for row in rows
        ]
        await self.repo.session.commit()
        return result

    async def publish_scope(self, key):
        publisher = ContextSnapshotPublisher(self.repo, self.storage, self.bucket)
        return await publisher.publish_scope(key)

    async def publish(self, user_id, project_id):
        await self.authorize(user_id, project_id)
        scopes = await self.scopes(user_id, project_id)
        keys = [row.scope_key for row in scopes]
        await self.repo.session.commit()
        return {key: await self.publish_scope(key) for key in keys}
