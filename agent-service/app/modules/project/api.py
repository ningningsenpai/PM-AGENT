"""项目 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.modules.project.dependencies import get_project_service
from app.modules.project.schemas import CreateProjectRequest
from app.modules.project.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["项目"])

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
