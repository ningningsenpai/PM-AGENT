
from __future__ import annotations

import asyncio
import json

from pydantic import ValidationError

from app.project.context.detail_analysis import FileDownloader, FileParserFactory
from app.project.context.detail_analysis.file_content import FileContent
from app.project.context.detail_analysis.schemas import (
    FileAnalysisRequest,
    FileAnalysisResult,
    FileDetail,
)

__all__ = ["FileDetailAnalysisService"]

from app.project.context.model import ProjectContextModelClient

from app.project.inner_prompts import ProjectFileDetailPrompt


class FileDetailAnalysisService:
    """ 负责下载并解析临时文件，并在处理结束后清理文件。"""

    def __init__(self) -> None:
        self.file_content = FileContent(FileDownloader(), FileParserFactory())
        self.client = ProjectContextModelClient()

    async def analyze(self, request: FileAnalysisRequest) -> FileAnalysisResult:
        """结合请求元数据和文件内容生成结构化文件详情。"""
        try:
            file_content = await self.file_content.get_content(
                request.file_url,
                request.file_type,
            )
        except Exception:
            return self._failed(request, "文件下载或解析失败")
        return await self._analyze_content(request, file_content.get("content", ""))

    async def analyze_bytes(
        self,
        request: FileAnalysisRequest,
        content: bytes,
    ) -> FileAnalysisResult:
        """直接解析对象存储字节，不再依赖临时下载地址。"""
        try:
            file_content = await self.file_content.get_content_from_bytes(
                content,
                request.file_type,
                request.filename,
            )
        except Exception:
            return self._failed(request, "文件解析失败")
        return await self._analyze_content(request, file_content.get("content", ""))

    async def _analyze_content(
        self,
        request: FileAnalysisRequest,
        content: str,
    ) -> FileAnalysisResult:
        metadata = {
            "project_id": request.project_id,
            "file_id": request.file_id,
            "business": request.business,
            "filename": request.filename,
            "file_type": request.file_type,
            "storage_uuid": request.storage_uuid,
            "storage_name": request.storage_name,
            "detail_ref": request.detail_ref,
            "original_path": request.original_path,
            "minio_path": request.minio_path,
            "size_bytes": request.size_bytes,
            "content_type": request.content_type,
            "content_hash": request.content_hash,
            "analysis_version": request.analysis_version,
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        prompt = (
            f"{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value}"
            f"\n\n# 文件元数据\n{metadata_json}"
            f"\n\n# 待分析文件内容\n<source_file>\n{content}\n</source_file>"
            f"\n\n{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL_FINAL_CHECK.value}"
        )
        try:
            response = await asyncio.to_thread(
                self.client.generate,
                prompt,
                response_format="json",
            )
        except Exception:
            return self._failed(request, "模型分析失败")

        try:
            detail = FileDetail.model_validate_json(response.content)
            self._validate_detail_identity(request, detail)
        except (ValidationError, ValueError):
            return FileAnalysisResult(
                project_id=request.project_id,
                file_id=request.file_id,
                content_hash=request.content_hash,
                analysis_version=request.analysis_version,
                status="failed",
                error_code="FILE_DETAIL_MODEL_OUTPUT_INVALID",
                error_message="模型返回的文件详情格式不正确",
            )

        return FileAnalysisResult(
            project_id=request.project_id,
            file_id=request.file_id,
            content_hash=request.content_hash,
            analysis_version=request.analysis_version,
            status="success",
            detail=detail,
        )

    @staticmethod
    def _failed(
        request: FileAnalysisRequest,
        message: str,
    ) -> FileAnalysisResult:
        return FileAnalysisResult(
            project_id=request.project_id,
            file_id=request.file_id,
            content_hash=request.content_hash,
            analysis_version=request.analysis_version,
            status="failed",
            error_code="FILE_DETAIL_ANALYSIS_FAILED",
            error_message=message,
        )

    @staticmethod
    def _validate_detail_identity(request: FileAnalysisRequest, detail: FileDetail,) -> None:
        """ 校验解析前后关键数据字段的值是否一致 """
        if (
            detail.project_id != request.project_id
            or detail.file_id != request.file_id
            or detail.storage_uuid != request.storage_uuid
            or detail.storage_name != request.storage_name
            or detail.detail_ref != request.detail_ref
            or detail.original_path != request.original_path
            or detail.minio_path != request.minio_path
            or detail.size_bytes != request.size_bytes
            or detail.content_type != request.content_type
            or detail.content_hash != request.content_hash
            or detail.analysis_version != request.analysis_version
        ):
            raise ValueError("文件详情身份字段与请求不一致")
