"""查询当前用户项目列表的只读 Agent 工具。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.agents.tools.base import BaseAgentTool
from app.agents.tools.schemas import ToolExecutionContext
from app.modules.project.service import ProjectService


class ListOwnedProjectsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OwnedProjectItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ListOwnedProjectsOutput(BaseModel):
    projects: list[OwnedProjectItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class ListOwnedProjectsTool(BaseAgentTool):
    """通过 ProjectService 查询当前登录用户拥有的项目。"""

    name = "list_owned_projects"
    description = "查询当前登录用户拥有的项目列表，包括名称、状态和创建更新时间。"
    input_model = ListOwnedProjectsInput
    output_model = ListOwnedProjectsOutput

    def __init__(self, projects: ProjectService) -> None:
        self._projects = projects

    async def execute(
        self,
        context: ToolExecutionContext,
        arguments: BaseModel,
    ) -> BaseModel:
        del arguments
        projects = await self._projects.list_owned(context.user_id)
        items = [OwnedProjectItem.model_validate(project) for project in projects]
        return ListOwnedProjectsOutput(projects=items, total=len(items))
