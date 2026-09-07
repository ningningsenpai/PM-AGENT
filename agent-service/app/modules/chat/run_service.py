"""运行幂等、会话租约和结果归档。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import get_snowflake_id_generator
from app.llm.telemetry import safe_payload

from .models import AgentRun


def next_id():
    return get_snowflake_id_generator().next_id()


class RunService:
    def __init__(self, repository, projects):
        self.repo = repository
        self.projects = projects

    async def start(
        self,
        user_id,
        project_id,
        operation,
        key,
        payload,
        trace_id,
        conversation_id=None,
    ):
        if not key or len(key) > 128:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        await self.projects.get_owned(user_id, project_id)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "project": project_id,
                    "conversation": conversation_id,
                    "payload": payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        conversation = None
        if conversation_id is not None:
            conversation = await self.repo.conversation(
                user_id, conversation_id, lock=True
            )
            if conversation is None or conversation.project_id != project_id:
                raise AppException(ErrorCode.FORBIDDEN, "会话不存在或无权访问")
        existing = await self.repo.duplicate(user_id, operation, key)
        if existing:
            if existing.request_hash != fingerprint:
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同请求")
            # 进程中断留下的运行不会无限占用会话；保留失败记录，重试须使用新键。
            if (
                existing.status == "running"
                and conversation
                and conversation.busy_until
                and conversation.busy_until < datetime.now(UTC).replace(tzinfo=None)
            ):
                existing.status = "failed"
                existing.error = "运行租约已过期，可能因服务重启中断"
                conversation.active_run_id = None
                conversation.busy_until = None
            await self.repo.session.commit()
            return existing, False
        if conversation and conversation.active_run_id:
            if conversation.busy_until and conversation.busy_until > datetime.now(UTC).replace(tzinfo=None):
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "会话仍有运行中的请求")
            previous = await self.repo.run(user_id, conversation.active_run_id)
            if previous and previous.status == "running":
                previous.status, previous.error = "failed", "运行租约已过期"
        run = AgentRun(
            id=next_id(),
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            operation=operation,
            request_key=key,
            request_hash=fingerprint,
            trace_id=trace_id,
            status="running",
            events=[],
            result={},
        )
        if conversation:
            conversation.active_run_id = run.id
            # 单轮至多五次 180 秒模型交互，预留工具与发布耗时。
            conversation.busy_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=20)
        try:
            await self.repo.add(run)
            await self.repo.session.commit()
        except IntegrityError:
            await self.repo.session.rollback()
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "相同幂等请求正在处理，请查询原运行"
            ) from None
        return run, True

    async def finish(self, run_id, user_id, events, result=None, error=None):
        run = await self.repo.run(user_id, run_id)
        run.events = safe_payload(events)
        run.result = safe_payload(result or {})
        run.status = "failed" if error else "success"
        run.error = error
        if run.conversation_id:
            conversation = await self.repo.conversation(
                user_id, run.conversation_id, lock=True
            )
            if conversation and conversation.active_run_id == run.id:
                conversation.active_run_id = None
                conversation.busy_until = None
        await self.repo.session.commit()
        return self.view(run)

    @staticmethod
    def view(run):
        return {
            "runId": str(run.id),
            "projectId": str(run.project_id),
            "conversationId": str(run.conversation_id) if run.conversation_id else None,
            "operation": run.operation,
            "status": run.status,
            "traceId": run.trace_id,
            "result": run.result,
            "error": run.error,
            "events": run.events,
        }

    async def get(self, user_id, run_id):
        run = await self.repo.run(user_id, run_id)
        if run is None:
            raise AppException(ErrorCode.FORBIDDEN, "运行不存在或无权访问")
        await self.projects.get_owned(user_id, run.project_id)
        result = self.view(run)
        await self.repo.session.commit()
        return result
