"""项目文件同步规划 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.modules.project_file.sync.dependencies import get_project_file_sync_service
from app.modules.project_file.sync.schemas import ProjectFileSyncPlanRequest
from app.modules.project_file.sync.service import ProjectFileSyncService

router = APIRouter()


@router.post("/sync/plan", response_model=ApiResponse)
async def plan_project_file_sync(
    project_id: int,
    request: ProjectFileSyncPlanRequest,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileSyncService = Depends(get_project_file_sync_service),
) -> ApiResponse:
    return success(await service.plan(principal.user_id, project_id, request))
