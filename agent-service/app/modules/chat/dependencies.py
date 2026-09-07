"""会话、学习及报告业务依赖装配，不在 API 中直接访问基础设施。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import get_object_storage
from app.llm.factory import get_llm_client
from app.llm.structured import StructuredJsonGenerator
from app.modules.project.dependencies import get_project_service
from app.modules.project_file.management.dependencies import get_project_file_service
from app.modules.report.repository import ReportRepository
from app.modules.report.service import ReportService

from .context_service import ContextService
from .conversation_service import ConversationService
from .learning_service import LearningService
from .repository import ChatRepository
from .run_service import RunService


def get_chat_repository(session: AsyncSession = Depends(get_db_session)):
    return ChatRepository(session)


def get_run_service(
    repo=Depends(get_chat_repository), projects=Depends(get_project_service)
):
    return RunService(repo, projects)


def get_context_service(
    repo=Depends(get_chat_repository),
    projects=Depends(get_project_service),
    storage=Depends(get_object_storage),
):
    return ContextService(repo, projects, storage, get_settings().storage.bucket)


def get_conversation_service(
    repo=Depends(get_chat_repository),
    projects=Depends(get_project_service),
    runs=Depends(get_run_service),
    contexts=Depends(get_context_service),
):
    return ConversationService(repo, projects, runs, contexts)


def generator(max_tokens):
    settings = get_settings().llm
    return StructuredJsonGenerator(
        get_llm_client(settings.default_llm_provider, settings),
        max_tokens=max_tokens,
        timeout_seconds=180,
    )


def get_learning_service(
    repo=Depends(get_chat_repository),
    conversations=Depends(get_conversation_service),
    contexts=Depends(get_context_service),
    runs=Depends(get_run_service),
):
    return LearningService(
        repo,
        conversations,
        contexts,
        runs,
        generator(get_settings().llm.memory_max_tokens),
    )


def get_report_service(
    session=Depends(get_db_session),
    projects=Depends(get_project_service),
    files=Depends(get_project_file_service),
    contexts=Depends(get_context_service),
    runs=Depends(get_run_service),
):
    return ReportService(
        ReportRepository(session),
        projects,
        files,
        contexts,
        runs,
        generator(get_settings().llm.report_max_tokens),
    )
