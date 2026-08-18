"""项目问答 Agent 的请求级依赖装配。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.agents.tools import ToolExecutor, ToolRegistry
from app.agents.tools.project import (
    GetCurrentProjectTool,
    ListCurrentProjectFilesTool,
    ListOwnedProjectsTool,
)
from app.core.config import get_settings
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService
from app.modules.project_file.management.dependencies import (
    get_project_file_service,
)
from app.modules.project_file.management.service import ProjectFileService


def get_project_chat_agent(
    projects: Annotated[ProjectService, Depends(get_project_service)],
    project_files: Annotated[
        ProjectFileService,
        Depends(get_project_file_service),
    ],
) -> ProjectChatAgent:
    """只向当前请求注册经过审核的真实业务工具。"""
    registry = ToolRegistry(
        [
            GetCurrentProjectTool(projects),
            ListCurrentProjectFilesTool(project_files),
            ListOwnedProjectsTool(projects),
        ]
    )
    return ProjectChatAgent(
        get_settings().llm,
        registry,
        ToolExecutor(registry),
    )
