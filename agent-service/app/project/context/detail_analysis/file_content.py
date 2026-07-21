from __future__ import annotations

from pathlib import Path

from . import downloader
from .downloader import FileDownloader
from .parser.base import FileParseResult
from .parser.factory import FileParserFactory

__all__ = ["FileContent"]


class FileContent:
    """负责下载并解析临时文件，并在处理结束后清理文件。"""

    def __init__(
            self,
            file_downloader: FileDownloader,
            parser_factory: FileParserFactory
    ) -> None:
        self.file_downloader = file_downloader or FileDownloader()
        self.parser_factory = parser_factory or FileParserFactory()

    async def get_content(self,
        temp_url: str,
        file_type: str,
    ) -> FileParseResult:
        """下载并解析指定类型的临时文件。

        Args:
            temp_url: MinIO 临时下载地址。
            file_type: 文件类型，例如 markdown、code 或 doc。

        Returns:
            文件解析结果。
        """
        file_path: Path | None = None

        try:
            file_path = await self.file_downloader.download(temp_url)
            parser = self.parser_factory.get_parser(file_type, file_path.name)
            return await parser.parse(file_path)
        finally:
            if file_path:
                file_path.unlink(missing_ok=True)
