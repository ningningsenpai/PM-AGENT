"""项目模块公开依赖构造。"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.modules.project.repository import ProjectRepository
from app.modules.project.service import ProjectService
from app.project.context.index import ProjectIndexService
from app.project.context.specification import ProjectSpecificationService


def get_project_service(
    session: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ProjectService:
    """构造请求级项目 Service，供项目 API 和 Agent 工具共同复用。"""
    locations = StorageLocationFactory(get_settings().storage)
    return ProjectService(
        ProjectRepository(session),
        storage,
        locations,
        ProjectIndexService(storage, locations),
        ProjectSpecificationService(storage, locations),
    )
