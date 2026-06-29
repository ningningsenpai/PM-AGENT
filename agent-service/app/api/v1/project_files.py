"""用户 Project 文件树接口。"""
from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from minio.error import S3Error

from app.api.internal.minio_files import get_project_file_service
from app.project.files import FileTreeCommand, FileTreeResult, ProjectFileService
from app.project.files.tree_service import ProjectFileTreeService

__all__ = ["router"]

router = APIRouter(prefix="/api/v1/project/files", tags=["Project Files"])


def get_project_file_tree_service(
    file_service: ProjectFileService = Depends(get_project_file_service),
) -> ProjectFileTreeService:
    """获取项目文件树业务服务实例。"""
    return ProjectFileTreeService(file_service)


@router.post("/build", response_model=list[FileTreeResult])
async def build_project_file_tree(
    command: FileTreeCommand,
    service: ProjectFileTreeService = Depends(get_project_file_tree_service),
) -> list[FileTreeResult]:
    """构建项目文件树并上传符合规则的文件。"""
    try:
        return await service.build_tree(command)
    except Exception as error:
        _raise_file_tree_error(error)


@router.post("/update-tree", response_model=list[FileTreeResult])
async def update_project_file_tree(
    command: FileTreeCommand,
    service: ProjectFileTreeService = Depends(get_project_file_tree_service),
) -> list[FileTreeResult]:
    """更新项目文件树并同步 MinIO 差异。"""
    try:
        return await service.update_tree(command)
    except Exception as error:
        _raise_file_tree_error(error)


def _raise_file_tree_error(error: Exception) -> NoReturn:
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, S3Error):
        raise HTTPException(status_code=502, detail=f"文件存储服务异常：{error.message}") from error
    raise HTTPException(status_code=500, detail="文件树服务异常") from error
