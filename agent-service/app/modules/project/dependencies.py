"""项目模块公开依赖构造。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.identifiers import SnowflakeIdGenerator, get_snowflake_id_generator
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.modules.chat import ChatContextInitializationService
from app.modules.project.repository import ProjectRepository
from app.modules.project.service import ProjectService
from app.project_context.index import ProjectIndexService
from app.project_context.specification import ProjectSpecificationService


def get_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    id_generator: Annotated[
        SnowflakeIdGenerator, Depends(get_snowflake_id_generator)
    ],
) -> ProjectService:
    """构造请求级项目 Service，供项目 API 和 Agent 工具共同复用。"""
    locations = StorageLocationFactory(get_settings().storage)
    return ProjectService(
        ProjectRepository(session),
        id_generator,
        ProjectIndexService(storage, locations),
        ProjectSpecificationService(storage, locations),
        ChatContextInitializationService(storage, locations),
    )
