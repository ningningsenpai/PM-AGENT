"""Agent 侧项目归属校验与上下文召回门面。"""
from __future__ import annotations

from app.agents.tools.schemas import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.modules.project.service import ProjectService
from app.input_context import (
    InputContextRetrievalService,
    RetrievalQuery,
    RetrievalResult,
)


class AgentProjectContextRetriever:
    """在调用召回中心前通过公开项目 Service 校验资源归属。"""

    def __init__(
        self,
        projects: ProjectService,
        retrieval: InputContextRetrievalService,
    ) -> None:
        self._projects = projects
        self._retrieval = retrieval

    async def retrieve(
        self,
        context: ToolExecutionContext,
        request: RetrievalQuery,
    ) -> RetrievalResult:
        """使用可信执行上下文完成项目归属校验和召回。"""
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        await self._projects.get_owned(context.user_id, context.project_id)
        return await self._retrieval.retrieve(
            user_id=context.user_id,
            project_id=context.project_id,
            request=request,
            trace_id=context.trace_id,
        )
