"""项目 API。"""
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
from app.modules.project.index_service import ProjectIndexService
from app.modules.project.repository import ProjectRepository
from app.modules.project.schemas import CreateProjectRequest
from app.modules.project.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["项目"])


def get_project_service(
    session: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ProjectService:
    locations = StorageLocationFactory(get_settings().storage)
    index_service = ProjectIndexService(storage, locations)
    return ProjectService(
        ProjectRepository(session),
        storage,
        locations,
        index_service,
    )


@router.post("", response_model=ApiResponse)
async def create_project(
    request: CreateProjectRequest,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectService = Depends(get_project_service),
) -> ApiResponse:
    return success(await service.create(principal.user_id, request))


@router.get("", response_model=ApiResponse)
async def list_projects(
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectService = Depends(get_project_service),
) -> ApiResponse:
    return success(await service.list_owned(principal.user_id))


@router.get("/{project_id}", response_model=ApiResponse)
async def get_project(
    project_id: int,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectService = Depends(get_project_service),
) -> ApiResponse:
    return success(await service.get_owned(principal.user_id, project_id))


@router.delete("/{project_id}", response_model=ApiResponse)
async def delete_project(
    project_id: int,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectService = Depends(get_project_service),
) -> ApiResponse:
    await service.delete_owned(principal.user_id, project_id)
    return success()
