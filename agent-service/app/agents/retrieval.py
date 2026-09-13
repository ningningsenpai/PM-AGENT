"""Agent 侧项目归属校验与输入上下文门面。"""

from __future__ import annotations

from app.agents.tools.schemas import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.input_context import (
    InputContextRetrievalService,
    RetrievalQuery,
    RetrievalResult,
    UserInputContext,
    UserInputContextService,
)
from app.modules.project.service import ProjectService


class AgentInputContextGateway:
    """在任何项目对象读取前通过公开 ProjectService 校验归属。"""

    def __init__(
        self,
        projects: ProjectService,
        retrieval: InputContextRetrievalService,
        input_context: UserInputContextService | None = None,
        *,
        contexts=None,
    ) -> None:
        self._projects = projects
        self._retrieval = retrieval
        self._input_context = input_context or UserInputContextService(retrieval)
        self._contexts = contexts

    async def retrieve(
        self,
        context: ToolExecutionContext,
        request: RetrievalQuery,
    ) -> RetrievalResult:
        project_id = await self._owned_project_id(context)
        return await self._retrieval.retrieve(
            user_id=context.user_id,
            project_id=project_id,
            request=request,
            trace_id=context.trace_id,
        )

    async def prepare(
        self,
        context: ToolExecutionContext,
        raw_query: str,
    ) -> UserInputContext:
        project_id = await self._owned_project_id(context)
        result = await self._input_context.prepare(
            user_id=context.user_id,
            project_id=project_id,
            raw_query=raw_query,
            trace_id=context.trace_id,
        )
        if self._contexts is not None:
            result.learned_entries = await self._presentation_preferences(context)
            result.learned_terms = []
        return result

    async def _presentation_preferences(self, context) -> list[dict]:
        """只向表达层提供有效用户偏好，不把规则或记忆混入事实候选。"""
        entries = await self._contexts.list_entries(
            context.user_id,
            context.project_id,
            kind="habit",
        )
        return [
            {
                "id": entry["id"],
                "kind": "habit",
                "content": entry["content"],
                "conditions": entry.get("conditions", []),
                "version": entry["version"],
            }
            for entry in entries[:50]
            if entry.get("kind") == "habit" and entry.get("status") == "active"
        ]

    async def release_reads(self):
        if self._contexts is not None:
            await self._contexts.release_reads()

    async def _owned_project_id(self, context: ToolExecutionContext) -> int:
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        await self._projects.get_owned(context.user_id, context.project_id)
        return context.project_id


# 兼容现有测试和内部导入，新增代码统一使用 AgentInputContextGateway。
AgentProjectContextRetriever = AgentInputContextGateway
