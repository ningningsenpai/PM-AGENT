"""项目文件数据结构。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "FileBusiness",
    "FileDeleteResult",
    "FileDownloadResult",
    "FileTreeCommand",
    "FileTreeResult",
    "FileUploadResult",
]


class FileBusiness(str, Enum):
    """项目文件业务分类。"""

    PROJECT = "project"
    SYSTEM = "system"
    USER = "user"


class FileUploadResult(BaseModel):
    """文件上传或覆盖更新返回结果。"""

    bucket: str = Field(..., description="对象存储桶")
    object_name: str = Field(..., description="对象名称")
    file_name: str = Field(..., description="实际文件名")
    url_path: str = Field(..., description="可用于后续操作的网址路径")
    size: int = Field(..., description="文件大小，单位字节")
    content_type: str = Field(..., description="文件类型")


class FileTreeResult(BaseModel):
    """文件树构建或更新返回结果，用于 Java 模块批量落库。"""

    original_file_name: str = Field(..., description="原始文件名")
    original_path: str = Field(..., description="原始文件路径")
    is_delete: bool = Field(..., alias="_is_delete", description="是否为需要删除的文件路径")
    business: FileBusiness = Field(..., description="文件业务分类")
    file_info: FileUploadResult = Field(..., description="文件上传或覆盖更新返回结果")


class FileTreeCommand(BaseModel):
    """文件树构建或更新请求。"""

    root_path: str = Field(..., description="需要扫描的项目根目录")
    output_dir: str = Field(..., description="Project_Index.json文件输出目录")
    user_id: str = Field(..., description="用户 ID")
    project_id: str = Field(..., description="项目 ID")
    business: FileBusiness = Field(default=FileBusiness.PROJECT.value, description="文件业务分类")


class FileDeleteResult(BaseModel):
    """文件删除返回结果。"""

    deleted: bool = Field(..., description="是否删除成功")
    url_path: str = Field(..., description="被删除的文件路径")


class FileDownloadResult(BaseModel):
    """文件查询返回结果。"""

    bucket: str = Field(..., description="对象存储桶")
    object_name: str = Field(..., description="对象名称")
    file_name: str = Field(..., description="实际文件名")
    size: int = Field(..., description="文件大小，单位字节")
    content_type: str = Field(..., description="文件类型")
    url_path: str = Field(..., description="可用于后续操作的网址路径")
