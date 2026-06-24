"""文件上传接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from minio.error import S3Error

from app.core.config import get_settings
from app.schemas.errors import ErrorCode, get_error_message
from app.schemas.files import FileBusiness, FileDeleteResult, FileDownloadResult, FileUploadResult
from app.services.file_storage import MinIOFileStorage

router = APIRouter(prefix="/api/v1/files", tags=["Files"])


def get_file_storage() -> MinIOFileStorage:
    """获取文件存储服务实例。"""
    settings = get_settings()
    return MinIOFileStorage(settings.minio)


def _validate_path_owner(storage: MinIOFileStorage, url_path: str, x_user_id: str | None) -> None:
    """校验请求用户是否匹配文件路径用户。"""
    if x_user_id is not None and storage.get_path_user_id(url_path) != x_user_id:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))


def _raise_storage_error(error: Exception) -> None:
    """转换文件存储异常为中文接口错误。"""
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, S3Error):
        raise HTTPException(status_code=502, detail=f"文件存储服务异常：{error.message}") from error
    raise HTTPException(status_code=500, detail="文件服务异常") from error


@router.post("", response_model=FileUploadResult)
async def upload_file(
    user_id: str = Form(..., alias="userId"),
    project_id: str = Form(..., alias="projectId"),
    business: FileBusiness = Form(...),
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    storage: MinIOFileStorage = Depends(get_file_storage),
) -> FileUploadResult:
    """上传文件到 MinIO。"""
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.IDEMPOTENCY_KEY_MISSING))
    if x_user_id is not None and x_user_id != user_id:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))
    settings = get_settings()
    if len(file_bytes) > settings.minio.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超出限制")
    try:
        result = storage.upload_file(
            user_id=user_id,
            project_id=project_id,
            business=business,
            file_name=file.filename or "file",
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as error:
        _raise_storage_error(error)
    return FileUploadResult(**result)


@router.get("", response_model=FileDownloadResult)
def get_file(
    url_path: str = Query(..., alias="urlPath"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    storage: MinIOFileStorage = Depends(get_file_storage),
) -> FileDownloadResult:
    """查询文件元信息。"""
    try:
        _validate_path_owner(storage, url_path, x_user_id)
        result = storage.stat_file(url_path)
    except Exception as error:
        _raise_storage_error(error)
    return FileDownloadResult(**result)


@router.get("/download")
def download_file(
    url_path: str = Query(..., alias="urlPath"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    storage: MinIOFileStorage = Depends(get_file_storage),
) -> StreamingResponse:
    """下载文件内容。"""
    try:
        _validate_path_owner(storage, url_path, x_user_id)
        meta, content = storage.download_file(url_path)
    except Exception as error:
        _raise_storage_error(error)
    return StreamingResponse(
        iter([content]),
        media_type=meta["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{meta["file_name"]}"'},
    )


@router.put("", response_model=FileUploadResult)
async def replace_file(
    url_path: str = Query(..., alias="urlPath"),
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    storage: MinIOFileStorage = Depends(get_file_storage),
) -> FileUploadResult:
    """覆盖更新文件。"""
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.IDEMPOTENCY_KEY_MISSING))
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.PARAM_INVALID))
    try:
        _validate_path_owner(storage, url_path, x_user_id)
        result = storage.replace_file(
            url_path=url_path,
            file_name=file.filename or "file",
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as error:
        _raise_storage_error(error)
    return FileUploadResult(**result)


@router.delete("", response_model=FileDeleteResult)
def delete_file(
    url_path: str = Query(..., alias="urlPath"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    storage: MinIOFileStorage = Depends(get_file_storage),
) -> FileDeleteResult:
    """删除文件。"""
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail=get_error_message(ErrorCode.IDEMPOTENCY_KEY_MISSING))
    try:
        _validate_path_owner(storage, url_path, x_user_id)
        result = storage.delete_file(url_path)
    except Exception as error:
        _raise_storage_error(error)
    return FileDeleteResult(**result)
