"""项目文件管理模块公开依赖构造。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.idempotency import IdempotencyGuard, get_idempotency_guard
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService
from app.modules.project_file.management.service import ProjectFileService
from app.modules.project_file.repository import ProjectFileRepository
from app.project.context.index import ProjectIndexService


def get_project_file_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    projects: Annotated[ProjectService, Depends(get_project_service)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    idempotency: Annotated[IdempotencyGuard, Depends(get_idempotency_guard)],
) -> ProjectFileService:
    """构造请求级项目文件 Service，供文件 API 和 Agent 工具共同复用。"""
    settings = get_settings()
    locations = StorageLocationFactory(settings.storage)
    return ProjectFileService(
        ProjectFileRepository(session),
        projects,
        storage,
        locations,
        ProjectIndexService(storage, locations),
        idempotency,
        settings.file,
        settings.storage,
    )
