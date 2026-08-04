"""查询当前项目的只读 Agent 工具。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agents.tools.base import BaseAgentTool
from app.agents.tools.schemas import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.modules.project.service import ProjectService


class GetCurrentProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetCurrentProjectOutput(BaseModel):
    id: int
    project_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class GetCurrentProjectTool(BaseAgentTool):
    """通过 ProjectService 查询并校验当前用户拥有的项目。"""

    name = "get_current_project"
    description = "查询当前对话关联项目的名称、状态和创建更新时间。"
    input_model = GetCurrentProjectInput
    output_model = GetCurrentProjectOutput

    def __init__(self, projects: ProjectService) -> None:
        self._projects = projects

    async def execute(
        self,
        context: ToolExecutionContext,
        arguments: BaseModel,
    ) -> BaseModel:
        del arguments
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        project = await self._projects.get_owned(context.user_id, context.project_id)
        return GetCurrentProjectOutput.model_validate(
            project.model_dump(mode="python")
        )
