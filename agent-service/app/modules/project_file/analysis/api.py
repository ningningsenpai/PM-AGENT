"""项目文件分析 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.identifiers import SnowflakeId
from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.modules.project_file.analysis.dependencies import (
    get_project_file_analysis_service,
)
from app.modules.project_file.analysis.service import ProjectFileAnalysisService

router = APIRouter()


class ParseSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fileIds: list[int] = Field(min_length=1, max_length=100)


@router.post("/parse/init", response_model=ApiResponse)
async def initialize_project_file_analysis(
    project_id: SnowflakeId,
    force: bool = Query(default=False),
    selection: Annotated[ParseSelection | None, Body()] = None,
    idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileAnalysisService = Depends(get_project_file_analysis_service),
) -> ApiResponse:
    return success(
        await service.analyze_pending_files(
            principal.user_id,
            project_id,
            idempotency_key,
            force=force,
            **({"file_ids": selection.fileIds} if selection else {}),
        )
    )
