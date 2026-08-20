from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from ..downloader import FileDownloader
from .base import ExtractedFileContent
from .factory import FileContentExtractorFactory

__all__ = ["FileContentExtractionService"]


class FileContentExtractionService:
    """根据文件格式提取标准文本，并负责受控临时文件的清理。"""

    def __init__(
        self,
        file_downloader: FileDownloader,
        extractor_factory: FileContentExtractorFactory,
    ) -> None:
        self.file_downloader = file_downloader or FileDownloader()
        self.extractor_factory = extractor_factory or FileContentExtractorFactory()

    async def download_and_extract(
        self,
        temp_url: str,
        file_type: str,
    ) -> ExtractedFileContent:
        """从临时地址下载文件，再按指定类型提取内容。"""
        file_path: Path | None = None

        try:
            file_path = await self.file_downloader.download(temp_url)
            extractor = self.extractor_factory.get_extractor(file_type, file_path.name)
            return await extractor.extract(file_path)
        finally:
            if file_path:
                file_path.unlink(missing_ok=True)

    async def extract_from_bytes(
        self,
        source_bytes: bytes,
        file_type: str,
        file_name: str,
    ) -> ExtractedFileContent:
        """将源文件字节写入临时文件并按文件格式提取内容。"""
        suffix = Path(file_name).suffix
        file_path: Path | None = None
        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
                temporary_file.write(source_bytes)
                file_path = Path(temporary_file.name)
            extractor = self.extractor_factory.get_extractor(file_type, file_name)
            return await extractor.extract(file_path)
        finally:
            if file_path:
                file_path.unlink(missing_ok=True)
