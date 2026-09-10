"""运行幂等、会话租约和结果归档。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import get_snowflake_id_generator
from app.core.time import shanghai_now_naive
from app.llm.telemetry import safe_payload
from app.modules.chat.runs.models import AgentRun
from app.modules.chat.runs.repository import RunRepository


class RunService:
    _LEASE_DURATION = timedelta(seconds=120)
    _HEARTBEAT_INTERVAL_SECONDS = 30
    _CONVERSATION_LEASE_DURATION = timedelta(minutes=20)

    def __init__(
        self, repository, projects, conversation_repository, session_factory=None
    ):
        self.repo = repository
        self.projects = projects
        self.conversation_repo = conversation_repository
        self.session_factory = session_factory

    async def start(
        self,
        user_id,
        project_id,
        operation,
        key,
        payload,
        trace_id,
        conversation_id=None,
        exclusive_scope=None,
    ):
        """
        根据业务不同执行不同的幂等校验以及 MySQL lock 机制
        conversation_id = None -> 非对话请求，仅校 agent_run 验请求幂等
        conversation_id ！= None -> 对话请求，校验 agent_run 幂等以及为 lock agent_conversation 防止对话重复进行
        """
        key = (key or "").strip()
        if not key:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        if len(key) > 128:
            raise AppException(ErrorCode.PARAM_INVALID, "幂等键长度不能超过 128 个字符")
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
            conversation = await self.conversation_repo.conversation(
                user_id, conversation_id, lock=True
            )
            if conversation is None or conversation.project_id != project_id:
                raise AppException(ErrorCode.FORBIDDEN, "会话不存在或无权访问")
        existing = await self.repo.duplicate(user_id, operation, key)
        if existing:
            if existing.request_hash != fingerprint:
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同请求")
            self._expire_if_needed(existing, conversation)
            await self.repo.session.commit()
            return existing, False
        if conversation and conversation.active_run_id:
            if (
                conversation.busy_until
                and conversation.busy_until > shanghai_now_naive()
            ):
                raise AppException(ErrorCode.RESOURCE_CONFLICT, "会话仍有运行中的请求")
            previous = await self.repo.run(user_id, conversation.active_run_id)
            if previous and previous.status == "running":
                previous.status, previous.error = "failed", "运行租约已过期"
        if exclusive_scope:
            active = await self.repo.active_scope(exclusive_scope)
            if active:
                self._expire_if_needed(active)
                if active.active_scope_key:
                    raise AppException(
                        ErrorCode.RESOURCE_CONFLICT,
                        f"当前项目已有运行中的解析任务，运行编号：{active.id}",
                    )
        run = AgentRun(
            id=get_snowflake_id_generator().next_id(),
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            operation=operation,
            request_key=key,
            request_hash=fingerprint,
            trace_id=trace_id,
            active_scope_key=exclusive_scope,
            lease_until=self._lease_deadline() if exclusive_scope else None,
            status="running",
            events=[],
            result={},
        )
        if conversation:
            # 对话窗口幂等预防（业务完成之后 busy_until 会自动设置为NULL）相当于和前端协同预防重复处理
            conversation.active_run_id = run.id
            conversation.busy_until = (
                shanghai_now_naive() + self._CONVERSATION_LEASE_DURATION
            )
        try:
            await self.repo.add(run)
            await self.repo.session.commit()
        except IntegrityError:
            await self.repo.session.rollback()
            existing = await self.repo.duplicate(user_id, operation, key)
            if existing:
                if existing.request_hash == fingerprint:
                    return existing, False
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同请求"
                ) from None
            if exclusive_scope:
                active = await self.repo.active_scope(exclusive_scope)
                if active:
                    raise AppException(
                        ErrorCode.RESOURCE_CONFLICT,
                        f"当前项目已有运行中的解析任务，运行编号：{active.id}",
                    ) from None
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "相同幂等请求正在处理，请查询原运行"
            ) from None
        return run, True

    @classmethod
    def _lease_deadline(cls):
        """生成 120 秒项目解析滑动租约的到期时间。"""
        return shanghai_now_naive() + cls._LEASE_DURATION

    def _expire_if_needed(self, run, conversation=None):
        """释放进程中断遗留的过期租约，同时保留失败运行供调用方核对。"""
        if run.status != "running":
            return
        deadline = run.lease_until or (
            conversation.busy_until if conversation else None
        )
        if not deadline or deadline >= shanghai_now_naive():
            return
        run.status = "failed"
        run.error = "运行租约已过期，可能因服务重启中断"
        run.active_scope_key = None
        run.lease_until = None
        if conversation and conversation.active_run_id == run.id:
            conversation.active_run_id = None
            conversation.busy_until = None

    async def renew(self, run_id, user_id):
        """在请求会话内续租，供短阶段切换时立即刷新租约。"""
        run = await self.repo.run(user_id, run_id)
        if run and run.status == "running" and run.active_scope_key:
            run.lease_until = self._lease_deadline()
            await self.repo.session.commit()

    async def _heartbeat(self, run_id, user_id):
        """使用独立数据库会话续租，避免长模型调用占用请求事务。"""
        while True:
            await asyncio.sleep(self._HEARTBEAT_INTERVAL_SECONDS)
            async with self.session_factory() as session:
                renewed = await RunRepository(session).renew_lease(
                    user_id, run_id, self._lease_deadline()
                )
                await session.commit()
            if not renewed:
                return

    @asynccontextmanager
    async def keep_alive(self, run_id, user_id):
        """在长运行期间维持项目租约；测试或非项目运行可不配置独立会话。"""
        task = (
            asyncio.create_task(self._heartbeat(run_id, user_id))
            if self.session_factory is not None
            else None
        )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def ensure_active(self, run_id, user_id):
        """外部写入前确认运行仍持有有效租约，阻止过期执行继续发布。"""
        run = await self.repo.run(user_id, run_id, lock=True)
        if run is None:
            raise AppException(ErrorCode.RESOURCE_CONFLICT, "解析运行不存在")
        self._expire_if_needed(run)
        active = run.status == "running" and bool(run.active_scope_key)
        await self.repo.session.commit()
        if not active:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "解析运行已失效，禁止继续写入"
            )

    async def recover(self, user_id, project_id, operation, key):
        """按原幂等键查询并原子清理过期运行。"""
        key = (key or "").strip()
        if not key:
            raise AppException(ErrorCode.IDEMPOTENCY_KEY_MISSING)
        if len(key) > 128:
            raise AppException(ErrorCode.PARAM_INVALID, "幂等键长度不能超过 128 个字符")
        await self.projects.get_owned(user_id, project_id)
        run = await self.repo.duplicate(
            user_id,
            operation,
            key,
            project_id=project_id,
            lock=True,
        )
        if run is None:
            await self.repo.session.commit()
            return {
                "runId": None,
                "status": "absent",
                "retryable": True,
                "retryMode": "same_key",
                "leaseUntil": None,
                "result": None,
                "error": None,
            }
        self._expire_if_needed(run)
        status = run.status
        await self.repo.session.commit()
        return {
            "runId": str(run.id),
            "status": status,
            "retryable": status == "failed",
            "retryMode": "new_key" if status == "failed" else None,
            "leaseUntil": run.lease_until,
            "result": run.result or None,
            "error": run.error,
        }

    async def cancel(self, run_id, user_id, events):
        """请求取消时回滚未提交内容、保存已发生的调用并释放会话租约。"""
        await self.repo.session.rollback()
        return await self.finish(
            run_id, user_id, events, error="运行已取消，已保留调用记录"
        )

    async def finish(
        self,
        run_id,
        user_id,
        events,
        result=None,
        error=None,
        *,
        recover_failed=False,
    ):
        run = await self.repo.run(user_id, run_id, lock=True)
        if run is None:
            raise AppException(ErrorCode.RESOURCE_CONFLICT, "运行不存在，无法完成收尾")
        if run.status != "running" and not (recover_failed and run.status == "failed"):
            await self.repo.session.commit()
            return self.view(run)
        run.events = safe_payload(events)
        run.result = safe_payload(result or {})
        run.status = "failed" if error else "success"
        run.error = error
        run.active_scope_key = None
        run.lease_until = None
        if run.conversation_id:
            conversation = await self.conversation_repo.conversation(
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
        run = await self.repo.run(user_id, run_id, lock=True)
        if run is None:
            raise AppException(ErrorCode.FORBIDDEN, "运行不存在或无权访问")
        await self.projects.get_owned(user_id, run.project_id)
        conversation = None
        if run.conversation_id:
            conversation = await self.conversation_repo.conversation(
                user_id, run.conversation_id, lock=True
            )
        self._expire_if_needed(run, conversation)
        result = self.view(run)
        await self.repo.session.commit()
        return result
