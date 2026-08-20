from __future__ import annotations

import asyncio
from pathlib import Path

from .base import ExtractedFileContent

__all__ = [
    "CodeFileExtractor",
    "ConfigFileExtractor",
    "MarkdownFileExtractor",
    "TextFileExtractor",
]


class TextFileExtractor:
    """提取常见文本文件内容，并拒绝明显的二进制内容。"""

    def __init__(
        self,
        result_type: str = "text",
        language: str | None = None,
        max_file_size_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self._result_type = result_type
        self._language = language
        self._max_file_size_bytes = max_file_size_bytes

    async def extract(self, file_path: Path) -> ExtractedFileContent:
        extracted_text = await asyncio.to_thread(self._decode_text, file_path)
        result: ExtractedFileContent = {
            "type": self._result_type,
            "text": extracted_text,
        }
        if self._language:
            result["language"] = self._language
        return result

    def _decode_text(self, file_path: Path) -> str:
        if file_path.stat().st_size > self._max_file_size_bytes:
            raise ValueError("待提取文件大小超过允许上限")

        source_bytes = file_path.read_bytes()
        if source_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            return source_bytes.decode("utf-16")
        if b"\x00" in source_bytes[:4096]:
            raise ValueError("当前文本提取器不支持二进制文件")

        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return source_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法识别文件编码")


class CodeFileExtractor(TextFileExtractor):
    """提取源代码，并在结果中保留语言类型。"""

    def __init__(self, language: str) -> None:
        super().__init__(result_type="code", language=language)


class MarkdownFileExtractor(TextFileExtractor):
    """提取 Markdown 文档内容。"""

    def __init__(self) -> None:
        super().__init__(result_type="markdown", language="markdown")


class ConfigFileExtractor(TextFileExtractor):
    """提取项目配置及结构化文本内容。"""

    def __init__(self, language: str | None = None) -> None:
        super().__init__(result_type="config", language=language)
