"""项目上下文受控召回 Agent 工具。"""
from __future__ import annotations

from pydantic import BaseModel

from app.agents.retrieval import AgentProjectContextRetriever
from app.agents.tools.base import BaseAgentTool
from app.agents.tools.schemas import ToolExecutionContext
from app.input_context import RetrievalQuery, RetrievalResult


class RetrieveProjectContextTool(BaseAgentTool):
    """在前置证据不足时复用同一召回中心细化项目事实。"""

    name = "retrieve_project_context"
    description = (
        "从当前项目的规范、文件详情、记忆和必要的原文件中召回事实。"
        "当前上下文证据不足、需要换关键词或需要源码证据时调用；"
        "不得用它查询其他用户或项目。"
    )
    input_model = RetrievalQuery
    output_model = RetrievalResult
    timeout_seconds = 20.0

    def __init__(self, retriever: AgentProjectContextRetriever) -> None:
        self._retriever = retriever

    async def execute(
        self,
        context: ToolExecutionContext,
        arguments: BaseModel,
    ) -> BaseModel:
        request = RetrievalQuery.model_validate(arguments)
        return await self._retriever.retrieve(context, request)
