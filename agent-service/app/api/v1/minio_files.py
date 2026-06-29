"""MinIo文件接口。"""
from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from minio.error import S3Error

from app.api.internal.minio_files import (
    delete_project_file,
    download_project_file,
    get_project_file_service,
    update_project_file,
    upload_project_file,
    view_project_file,
)
from app.project.files import FileBusiness, FileDeleteResult, FileDownloadResult, FileUploadResult, ProjectFileService

__all__ = ["router"]

router = APIRouter(prefix="/api/v1/minio/files", tags=["MinIo Files"])


@router.post("/upload", response_model=FileUploadResult)
async def upload_file(
    project_id: str = Form(..., alias="projectId"),
    business: FileBusiness = Form(...),
    file: UploadFile = File(...),
    user_id: str = Form(..., alias="userId"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileUploadResult:
    """上传项目文件。"""
    try:
        return await upload_project_file(
            project_id=project_id,
            business=business,
            file=file,
            user_id=user_id,
            service=service,
        )
    except Exception as error:
        _raise_file_error(error)


@router.get("/view", response_model=FileDownloadResult)
def get_file(
    url_path: str = Query(..., alias="urlPath"),
    current_user_id: str | None = Query(default=None, alias="currentUserId"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileDownloadResult:
    """查询项目文件元信息。"""
    try:
        return view_project_file(
            url_path=url_path,
            current_user_id=current_user_id,
            service=service,
        )
    except Exception as error:
        _raise_file_error(error)


@router.get("/download")
def download_file(
    url_path: str = Query(..., alias="urlPath"),
    current_user_id: str | None = Query(default=None, alias="currentUserId"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> StreamingResponse:
    """下载项目文件内容。"""
    try:
        meta, content = download_project_file(
            url_path=url_path,
            current_user_id=current_user_id,
            service=service,
        )
    except Exception as error:
        _raise_file_error(error)
    return StreamingResponse(
        iter([content]),
        media_type=meta.content_type,
        headers={"Content-Disposition": f'attachment; filename="{meta.file_name}"'},
    )


@router.put("/update", response_model=FileUploadResult)
async def replace_file(
    url_path: str = Query(..., alias="urlPath"),
    file: UploadFile = File(...),
    current_user_id: str | None = Form(default=None, alias="currentUserId"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileUploadResult:
    """覆盖更新项目文件。"""
    try:
        return await update_project_file(
            url_path=url_path,
            file=file,
            current_user_id=current_user_id,
            service=service,
        )
    except Exception as error:
        _raise_file_error(error)



@router.delete("/delete", response_model=FileDeleteResult)
def delete_file(
    url_path: str = Query(..., alias="urlPath"),
    current_user_id: str | None = Query(default=None, alias="currentUserId"),
    service: ProjectFileService = Depends(get_project_file_service),
) -> FileDeleteResult:
    """删除项目文件。"""
    try:
        return delete_project_file(
            url_path=url_path,
            current_user_id=current_user_id,
            service=service,
        )
    except Exception as error:
        _raise_file_error(error)


def _raise_file_error(error: Exception) -> NoReturn:
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, S3Error):
        raise HTTPException(status_code=502, detail=f"文件存储服务异常：{error.message}") from error
    raise HTTPException(status_code=500, detail="文件服务异常") from error
