"""项目文件分析 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.infrastructure.database import get_db_session
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
    get_object_storage,
)
from app.modules.project.api import get_project_service
from app.modules.project.index_service import ProjectIndexService
from app.modules.project.service import ProjectService
from app.modules.project_file.analysis.service import ProjectFileAnalysisService
from app.modules.project_file.repository import ProjectFileRepository
from app.project.context.detail_analysis.service import FileDetailAnalysisService

router = APIRouter()


def get_project_file_analysis_service(
    session: AsyncSession = Depends(get_db_session),
    projects: ProjectService = Depends(get_project_service),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ProjectFileAnalysisService:
    locations = StorageLocationFactory(get_settings().storage)
    return ProjectFileAnalysisService(
        ProjectFileRepository(session),
        projects,
        storage,
        locations,
        ProjectIndexService(storage, locations),
        FileDetailAnalysisService(),
    )


@router.post("/parse/init", response_model=ApiResponse)
async def initialize_project_file_parse(
    project_id: int,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileAnalysisService = Depends(
        get_project_file_analysis_service
    ),
) -> ApiResponse:
    await service.initialize(principal.user_id, project_id)
    return success()
