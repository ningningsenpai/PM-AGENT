"""项目问答 Agent 的请求级依赖装配。"""
from __future__ import annotations

from fastapi import Depends

from app.agents.tools import ToolExecutor, ToolRegistry
from app.agents.tools.project import GetCurrentProjectTool
from app.core.config import get_settings
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService


def get_project_chat_agent(
    projects: ProjectService = Depends(get_project_service),
) -> ProjectChatAgent:
    """只向当前请求注册经过审核的真实业务工具。"""
    registry = ToolRegistry([GetCurrentProjectTool(projects)])
    return ProjectChatAgent(
        get_settings().llm,
        registry,
        ToolExecutor(registry),
    )
