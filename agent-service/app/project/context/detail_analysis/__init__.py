"""单文件完整详情解析链路。"""

from .downloader import FileDownloader
from .parser import FileParseResult, FileParser, FileParserFactory

__all__ = [
    "FileDetailAnalysisService",
    "FileDownloader",
    "FileParseResult",
    "FileParser",
    "FileParserFactory",
]
