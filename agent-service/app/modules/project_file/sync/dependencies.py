"""项目文件同步规划依赖。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database import get_db_session
from app.modules.project.dependencies import get_project_service
from app.modules.project.service import ProjectService
from app.modules.project_file.repository import ProjectFileRepository
from app.modules.project_file.sync.domain import ProjectFileSyncPlanner
from app.modules.project_file.sync.service import ProjectFileSyncService


def get_project_file_sync_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    projects: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectFileSyncService:
    return ProjectFileSyncService(
        ProjectFileRepository(session),
        projects,
        ProjectFileSyncPlanner(),
        get_settings().file,
    )
