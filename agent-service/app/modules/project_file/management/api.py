"""项目文件管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile

from app.core.config import get_settings
from app.core.response import ApiResponse, success
from app.core.security import AuthPrincipal, require_principal
from app.modules.project_file.management.dependencies import (
    get_project_file_service,
)
from app.modules.project_file.management.schemas import UpdateProjectFilePathRequest
from app.modules.project_file.management.service import ProjectFileService

router = APIRouter()


@router.post("", response_model=ApiResponse)
async def upload_project_file(
    project_id: int,
    relative_path: str = Form(alias="relativePath"),
    source_mtime_ms: int = Form(alias="sourceMtimeMs"),
    file: UploadFile = File(),
    idempotency_key: str | None = Header(
        default=None,
        alias="X-Idempotency-Key",
    ),
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    content = await file.read(get_settings().file.max_size_bytes + 1)
    return success(
        await service.upload(
            principal.user_id,
            project_id,
            idempotency_key,
            relative_path,
            source_mtime_ms,
            content,
            file.content_type,
        )
    )


@router.put("/{file_id}/content", response_model=ApiResponse)
async def overwrite_project_file(
    project_id: int,
    file_id: int,
    source_mtime_ms: int = Form(alias="sourceMtimeMs"),
    lock_version: int = Form(alias="lockVersion"),
    file: UploadFile = File(),
    idempotency_key: str | None = Header(
        default=None,
        alias="X-Idempotency-Key",
    ),
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    content = await file.read(get_settings().file.max_size_bytes + 1)
    return success(
        await service.overwrite(
            principal.user_id,
            project_id,
            file_id,
            idempotency_key,
            source_mtime_ms,
            lock_version,
            content,
            file.content_type,
        )
    )


@router.patch("/{file_id}/path", response_model=ApiResponse)
async def update_project_file_path(
    project_id: int,
    file_id: int,
    request: UpdateProjectFilePathRequest,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    return success(
        await service.update_path(
            principal.user_id,
            project_id,
            file_id,
            request,
        )
    )


@router.get("", response_model=ApiResponse)
async def list_project_files(
    project_id: int,
    business_code: str | None = Query(default=None, alias="businessCode"),
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    return success(
        await service.list_files(
            principal.user_id,
            project_id,
            business_code,
        )
    )


@router.get("/{file_id}/read-url", response_model=ApiResponse)
async def create_project_file_read_url(
    project_id: int,
    file_id: int,
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    return success(
        await service.create_read_url(
            principal.user_id,
            project_id,
            file_id,
        )
    )


@router.delete("/{file_id}", response_model=ApiResponse)
async def delete_project_file(
    project_id: int,
    file_id: int,
    lock_version: int = Query(alias="lockVersion"),
    principal: AuthPrincipal = Depends(require_principal),
    service: ProjectFileService = Depends(get_project_file_service),
) -> ApiResponse:
    await service.delete(
        principal.user_id,
        project_id,
        file_id,
        lock_version,
    )
    return success()
