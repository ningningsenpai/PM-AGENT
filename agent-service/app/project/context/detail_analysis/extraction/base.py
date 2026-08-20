from __future__ import annotations

from pathlib import Path
from typing import NotRequired, Protocol, TypedDict

__all__ = ["ExtractedFileContent", "FileContentExtractor"]


class ExtractedFileContent(TypedDict):
    """文件内容提取的统一返回结构。"""

    type: str
    text: str
    language: NotRequired[str]


class FileContentExtractor(Protocol):
    """所有文件内容提取器必须实现的异步接口。"""

    async def extract(self, file_path: Path) -> ExtractedFileContent: ...
