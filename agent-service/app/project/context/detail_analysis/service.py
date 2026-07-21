
from __future__ import annotations

from app.project.context.detail_analysis import FileDownloader, FileParserFactory
from app.project.context.detail_analysis.file_content import FileContent
from app.project.context.detail_analysis.schemas import FileAnalysisResult

__all__ = ["FileDetailAnalysisService"]

from app.project.context.model import ProjectContextModelClient, ProjectContextModelResponse

from app.project.inner_prompts import ProjectFileDetailPrompt


class FileDetailAnalysisService:
    """ 负责下载并解析临时文件，并在处理结束后清理文件。"""
    def __init__(self) -> None:
        self.file_content = FileContent(FileDownloader(), FileParserFactory())
        self.client = ProjectContextModelClient()

    """ 分析文件详情
        @param file_url: 文件 MinIO 临时下载地址
        @param file_type: 文件类型，例如 markdown、code 或 doc。
        @return: FileAnalysisResult 文件详情分析结果
    """
    async def analyze(self, file_url: str, file_type: str) -> ProjectContextModelResponse:
        file_content = await self.file_content.get_content(file_url, file_type)

        content = file_content.get("content", "")
        prompt = (
            f"{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value}"
            f"\n\n# 待分析文件内容\n{content}"
        )

        return self.client.generate(prompt)







