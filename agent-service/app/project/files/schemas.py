"""项目文件数据结构。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "FileBusiness",
    "FileDeleteResult",
    "FileDownloadResult",
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
