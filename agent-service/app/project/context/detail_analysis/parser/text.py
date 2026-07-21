from __future__ import annotations

import asyncio
from pathlib import Path

from .base import FileParseResult

__all__ = [
    "CodeFileParser",
    "ConfigFileParser",
    "MarkdownFileParser",
    "TextFileParser",
]


class TextFileParser:
    """解析常见文本文件，并拒绝明显的二进制内容。"""

    def __init__(
        self,
        result_type: str = "text",
        language: str | None = None,
        max_file_size_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self._result_type = result_type
        self._language = language
        self._max_file_size_bytes = max_file_size_bytes

    async def parse(self, file_path: Path) -> FileParseResult:
        content = await asyncio.to_thread(self._read_text, file_path)
        result: FileParseResult = {
            "type": self._result_type,
            "content": content,
        }
        if self._language:
            result["language"] = self._language
        return result

    def _read_text(self, file_path: Path) -> str:
        if file_path.stat().st_size > self._max_file_size_bytes:
            raise ValueError("待解析文件大小超过允许上限")

        content = file_path.read_bytes()
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return content.decode("utf-16")
        if b"\x00" in content[:4096]:
            raise ValueError("当前文本解析器不支持二进制文件")

        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法识别文件编码")


class CodeFileParser(TextFileParser):
    """解析源代码，并在结果中保留语言类型。"""

    def __init__(self, language: str) -> None:
        super().__init__(result_type="code", language=language)


class MarkdownFileParser(TextFileParser):
    """解析 Markdown 文档。"""

    def __init__(self) -> None:
        super().__init__(result_type="markdown", language="markdown")


class ConfigFileParser(TextFileParser):
    """解析项目配置及结构化文本文件。"""

    def __init__(self, language: str | None = None) -> None:
        super().__init__(result_type="config", language=language)
