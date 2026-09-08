"""项目问答 Agent 的请求级依赖装配。"""

from __future__ import annotations

from typing import Annotated

from app.agents.retrieval import AgentInputContextGateway
from app.agents.tools import ToolExecutor, ToolRegistry
from app.agents.tools.context import (
    GetContextChangesTool,
    GetProjectReportTool,
    ListContextEntriesTool,
    ReadProjectFileEvidenceTool,
)
from app.agents.tools.project import (
    GetCurrentProjectTool,
    ListCurrentProjectFilesTool,
    ListOwnedProjectsTool,
    RetrieveProjectContextTool,
)
from app.core.config import get_settings
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.input_context import (
    InputContextRetrievalService,
    NormalizationService,
    UserInputContextService,
)
from app.input_context.dependencies import get_normalization_service
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.modules.chat.context_service import ContextService
from app.modules.chat.dependencies import get_context_service
from app.modules.report.dependencies import get_report_service
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService
from app.modules.project_file.management.dependencies import (
    get_project_file_service,
)
from app.modules.project_file.management.service import ProjectFileService
from app.modules.report.service import ReportService
from app.project_context.file_detail import FileDownloader
from app.project_context.file_detail.extraction import (
    FileContentExtractionService,
    FileContentExtractorFactory,
)
from fastapi import Depends


def get_project_chat_agent(
    projects: Annotated[ProjectService, Depends(get_project_service)],
    project_files: Annotated[
        ProjectFileService,
        Depends(get_project_file_service),
    ],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    normalization: Annotated[
        NormalizationService,
        Depends(get_normalization_service),
    ],
    contexts: Annotated[ContextService, Depends(get_context_service)],
    reports: Annotated[ReportService, Depends(get_report_service)],
) -> ProjectChatAgent:
    """只向当前请求注册经过审核的真实业务工具。"""
    settings = get_settings()
    retrieval = InputContextRetrievalService(
        storage,
        StorageLocationFactory(settings.storage),
        normalization,
        FileContentExtractionService(
            FileDownloader(),
            FileContentExtractorFactory(),
        ),
    )
    gateway = AgentInputContextGateway(
        projects,
        retrieval,
        UserInputContextService(retrieval),
        contexts=contexts,
    )
    registry = ToolRegistry(
        [
            GetCurrentProjectTool(projects),
            ListCurrentProjectFilesTool(project_files),
            ListOwnedProjectsTool(projects),
            RetrieveProjectContextTool(gateway),
            ListContextEntriesTool(contexts),
            GetContextChangesTool(contexts),
            GetProjectReportTool(reports),
            ReadProjectFileEvidenceTool(project_files),
        ]
    )
    return ProjectChatAgent(
        settings.llm,
        registry,
        ToolExecutor(registry),
        gateway,
    )
