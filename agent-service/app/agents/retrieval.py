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
    ) -> None:
        self._projects = projects
        self._retrieval = retrieval
        self._input_context = input_context or UserInputContextService(retrieval)

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
        return await self._input_context.prepare(
            user_id=context.user_id,
            project_id=project_id,
            raw_query=raw_query,
            trace_id=context.trace_id,
        )

    async def _owned_project_id(self, context: ToolExecutionContext) -> int:
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        await self._projects.get_owned(context.user_id, context.project_id)
        return context.project_id


# 兼容现有测试和内部导入，新增代码统一使用 AgentInputContextGateway。
AgentProjectContextRetriever = AgentInputContextGateway
