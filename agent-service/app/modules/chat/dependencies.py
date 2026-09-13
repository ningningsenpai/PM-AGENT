"""Chat 公开依赖装配；各仓储共享缓存的请求级数据库 Session。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_db_session, get_session_factory
from app.infrastructure.storage import ObjectStorage, get_object_storage
from app.llm.dependencies import get_structured_generator
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService

from .context.repository import ContextRepository
from .context.automatic_update import AutomaticContextUpdateService
from .context.service import ContextService
from .conversation.repository import ConversationRepository
from .conversation.service import ConversationService
from .learning.repository import LearningDraftRepository
from .learning.service import LearningService
from .request_understanding.service import RequestUnderstandingService
from .runs.repository import RunRepository
from .runs.service import RunService

Session = Annotated[AsyncSession, Depends(get_db_session)]
Projects = Annotated[ProjectService, Depends(get_project_service)]


def get_conversation_repository(session: Session) -> ConversationRepository:
    return ConversationRepository(session)


def get_context_repository(session: Session) -> ContextRepository:
    return ContextRepository(session)


def get_run_repository(session: Session) -> RunRepository:
    return RunRepository(session)


def get_learning_draft_repository(session: Session) -> LearningDraftRepository:
    return LearningDraftRepository(session)


def get_run_service(
    repo: Annotated[RunRepository, Depends(get_run_repository)],
    projects: Projects,
    conversations: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
) -> RunService:
    return RunService(repo, projects, conversations, get_session_factory())


def get_context_service(
    repo: Annotated[ContextRepository, Depends(get_context_repository)],
    projects: Projects,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> ContextService:
    return ContextService(repo, projects, storage, get_settings().storage.bucket)


def get_conversation_service(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    projects: Projects,
    runs: Annotated[RunService, Depends(get_run_service)],
    contexts: Annotated[ContextService, Depends(get_context_service)],
    drafts: Annotated[LearningDraftRepository, Depends(get_learning_draft_repository)],
) -> ConversationService:
    return ConversationService(
        repo,
        projects,
        runs,
        contexts,
        RequestUnderstandingService(get_structured_generator(1200)),
        AutomaticContextUpdateService(contexts, drafts),
    )


def get_learning_service(
    repo: Annotated[ContextRepository, Depends(get_context_repository)],
    messages: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    conversations: Annotated[ConversationService, Depends(get_conversation_service)],
    contexts: Annotated[ContextService, Depends(get_context_service)],
    runs: Annotated[RunService, Depends(get_run_service)],
    drafts: Annotated[LearningDraftRepository, Depends(get_learning_draft_repository)],
) -> LearningService:
    return LearningService(
        repo,
        messages,
        conversations,
        contexts,
        runs,
        get_structured_generator(get_settings().llm.memory_max_tokens),
        drafts,
    )
