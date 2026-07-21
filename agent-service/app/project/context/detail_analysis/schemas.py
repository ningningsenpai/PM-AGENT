
from __future__ import annotations
from dataclasses import dataclass

__all__ = [
    "FileAnalysisRequest",
    "FileAnalysisResult",
]


@dataclass(frozen=True)
class FileAnalysisRequest:
    """ 文件 HTTP 请求传递的参数 """
    userId: int
    projectId: int
    business: str
    fileId: int
    filename: str
    storage_name: str
    content_type: str


@dataclass(frozen=True)
class FileAnalysisResult:
    """ 文件 HTTP 响应返回的参数 """
