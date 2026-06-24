"""项目文件接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from minio.error import S3Error

from app.core.config import get_settings
from app.core.request_context import get_request_context
from app.project.files import FileBusiness, FileDeleteResult, FileDownloadResult, FileUploadResult, ProjectFileService
from app.schemas.errors import ErrorCode, get_error_message

__all__ = ["legacy_router", "router"]

router = APIRouter(prefix="/api/v1/project/files", tags=["Project Files"])
legacy_router = APIRouter(prefix="/api/v1/files", tags=["Project Files"])


def get_project_file_service() -> ProjectFileService:
    """获取项目文件业务服务实例。"""
    return ProjectFileService(get_settings().minio)


@legacy_router.post("", response_model=FileUploadResult)
@router.post("", response_model=FileUploadResult)
async def upload_file(
    project_id: str = Form(..., alias="projectId"),
    business: FileBusiness = Form(...),
    file: UploadFile = File(...),
    user_id: str | None = Form(default=None, alias="userId"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileUploadResult:
    """上传项目文件。"""
    _validate_idempotency_key(x_idempotency_key)
    context = get_request_context()
    effective_user_id = _resolve_user_id(user_id, context.user_id)
    file_bytes = await file.read()
    try:
        result = service.upload_file(
            user_id=effective_user_id,
            project_id=project_id,
            business=business,
            file_name=file.filename or "file",
            file_bytes=file_bytes,
            content_type=file.content_type,
        )
    except Exception as error:
        _raise_file_error(error)
    return FileUploadResult(**result)


@legacy_router.get("", response_model=FileDownloadResult)
@router.get("", response_model=FileDownloadResult)
def get_file(
    url_path: str = Query(..., alias="urlPath"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileDownloadResult:
    """查询项目文件元信息。"""
    try:
        result = service.stat_file(url_path, get_request_context().user_id)
    except Exception as error:
        _raise_file_error(error)
    return FileDownloadResult(**result)


@legacy_router.get("/download")
@router.get("/download")
def download_file(
    url_path: str = Query(..., alias="urlPath"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> StreamingResponse:
    """下载项目文件内容。"""
    try:
        meta, content = service.download_file(url_path, get_request_context().user_id)
    except Exception as error:
        _raise_file_error(error)
    return StreamingResponse(
        iter([content]),
        media_type=meta["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{meta["file_name"]}"'},
    )


@legacy_router.put("", response_model=FileUploadResult)
@router.put("", response_model=FileUploadResult)
async def replace_file(
    url_path: str = Query(..., alias="urlPath"),
    file: UploadFile = File(...),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileUploadResult:
    """覆盖更新项目文件。"""
    _validate_idempotency_key(x_idempotency_key)
    file_bytes = await file.read()
    try:
        result = service.replace_file(
            url_path=url_path,
            file_bytes=file_bytes,
            content_type=file.content_type,
            current_user_id=get_request_context().user_id,
        )
    except Exception as error:
        _raise_file_error(error)
    return FileUploadResult(**result)


@legacy_router.delete("", response_model=FileDeleteResult)
@router.delete("", response_model=FileDeleteResult)
def delete_file(
    url_path: str = Query(..., alias="urlPath"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileDeleteResult:
    """删除项目文件。"""
    _validate_idempotency_key(x_idempotency_key)
    try:
        result = service.delete_file(url_path, get_request_context().user_id)
    except Exception as error:
        _raise_file_error(error)
    return FileDeleteResult(**result)


def _validate_idempotency_key(idempotency_key: str | None) -> None:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.IDEMPOTENCY_KEY_MISSING))


def _resolve_user_id(form_user_id: str | None, context_user_id: str | None) -> str:
    if context_user_id and form_user_id and context_user_id != form_user_id:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))
    user_id = context_user_id or form_user_id
    if not user_id:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))
    return user_id


def _raise_file_error(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, S3Error):
        raise HTTPException(status_code=502, detail=f"文件存储服务异常：{error.message}") from error
    raise HTTPException(status_code=500, detail="文件服务异常") from error
