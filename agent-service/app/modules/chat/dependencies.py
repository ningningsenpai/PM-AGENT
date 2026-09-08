"""Chat 业务依赖装配，不在 API 中直接访问基础设施。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import get_object_storage
from app.llm.dependencies import get_structured_generator
from app.modules.project.dependencies import get_project_service

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
        get_structured_generator(get_settings().llm.memory_max_tokens),
    )
