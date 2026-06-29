"""MinIO 文件接口内部函数。"""
from __future__ import annotations

from fastapi import UploadFile

from app.core.config import get_settings
from app.project.files import FileBusiness, FileDeleteResult, FileDownloadResult, FileUploadResult, ProjectFileService

__all__ = [
    "get_project_file_service",
    "upload_project_file",
    "view_project_file",
    "download_project_file",
    "update_project_file",
    "delete_project_file",
]


def get_project_file_service() -> ProjectFileService:
    """获取项目文件业务服务实例。"""
    config = get_settings()
    return ProjectFileService(config.storage.minio)


async def upload_project_file(
    *,
    project_id: str,
    business: FileBusiness,
    file: UploadFile,
    user_id: str,
    service: ProjectFileService,
) -> FileUploadResult:
    """上传项目文件并返回文件元信息。"""
    file_bytes = await file.read()
    result = service.upload_file(
        user_id=user_id,
        project_id=project_id,
        business=business,
        file_name=file.filename or "file",
        file_bytes=file_bytes,
        content_type=file.content_type,
    )
    return FileUploadResult(**result)


def view_project_file(
    *,
    url_path: str,
    current_user_id: str | None,
    service: ProjectFileService,
) -> FileDownloadResult:
    """查询项目文件元信息。"""
    result = service.stat_file(url_path, current_user_id)
    return FileDownloadResult(**result)


def download_project_file(
    *,
    url_path: str,
    current_user_id: str | None,
    service: ProjectFileService,
) -> tuple[FileDownloadResult, bytes]:
    """下载项目文件内容。"""
    meta, content = service.download_file(url_path, current_user_id)
    return FileDownloadResult(**meta), content


async def update_project_file(
    *,
    url_path: str,
    file: UploadFile,
    current_user_id: str | None,
    service: ProjectFileService,
) -> FileUploadResult:
    """覆盖更新项目文件。"""
    file_bytes = await file.read()
    result = service.replace_file(
        url_path=url_path,
        file_bytes=file_bytes,
        content_type=file.content_type,
        current_user_id=current_user_id,
    )
    return FileUploadResult(**result)


def delete_project_file(
    *,
    url_path: str,
    current_user_id: str | None,
    service: ProjectFileService,
) -> FileDeleteResult:
    """删除项目文件。"""
    result = service.delete_file(url_path, current_user_id)
    return FileDeleteResult(**result)
