from __future__ import annotations

from pathlib import Path
from typing import NotRequired, Protocol, TypedDict

__all__ = ["FileParseResult", "FileParser"]


class FileParseResult(TypedDict):
    """文件解析器的统一返回结构。"""

    type: str
    content: str
    language: NotRequired[str]


class FileParser(Protocol):
    """所有文件解析器必须实现的异步接口。"""

    async def parse(self, file_path: Path) -> FileParseResult: ...
