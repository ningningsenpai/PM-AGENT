"""项目文件分析 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.modules.project_file.analysis.dependencies import (
    get_project_file_analysis_service,
)
from app.modules.project_file.analysis.service import ProjectFileAnalysisService

router = APIRouter()


@router.post("/parse/init", response_model=ApiResponse)
async def initialize_project_file_analysis(
    project_id: int,
    force: bool = Query(default=False),
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileAnalysisService = Depends(get_project_file_analysis_service),
) -> ApiResponse:
    return success(
        await service.analyze_pending_files(
            principal.user_id,
            project_id,
            force=force,
        )
    )
