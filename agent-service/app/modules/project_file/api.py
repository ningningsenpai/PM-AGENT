"""项目文件公开 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.idempotency import IdempotencyGuard, get_idempotency_guard
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
from app.modules.project_file.analysis_service import ProjectFileAnalysisService
from app.modules.project_file.repository import ProjectFileRepository
from app.modules.project_file.schemas import UpdateProjectFilePathRequest
from app.modules.project_file.service import ProjectFileService
from app.project.context.detail_analysis.service import FileDetailAnalysisService

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/files",
    tags=["项目文件"],
)


def get_project_file_service(
    session: AsyncSession = Depends(get_db_session),
    projects: ProjectService = Depends(get_project_service),
    storage: ObjectStorage = Depends(get_object_storage),
    idempotency: IdempotencyGuard = Depends(get_idempotency_guard),
) -> ProjectFileService:
    settings = get_settings()
    locations = StorageLocationFactory(settings.storage)
    return ProjectFileService(
        ProjectFileRepository(session),
        projects,
        storage,
        locations,
        ProjectIndexService(storage, locations),
        idempotency,
        settings.file,
        settings.storage,
    )


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
