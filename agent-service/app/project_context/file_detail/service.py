"""文件语义分析服务。"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import ValidationError

from app.core.logger import get_logger
from app.llm.prompts.project_context import ProjectFileDetailPrompt
from app.llm.structured import StructuredJsonGenerator
from app.project_context.file_detail.extraction import ExtractedFileContent
from app.project_context.file_detail.schemas import (
    FileDetail,
    FileDetailSemanticOutput,
    FileSemanticAnalysisRequest,
    FileSemanticAnalysisResult,
)
from app.project_context.file_detail.sensitive_content import (
    SensitiveContentBlockedError,
    sanitize_sensitive_content,
)

__all__ = ["FileSemanticAnalysisService"]

logger = get_logger(__name__)


class FileSemanticAnalysisService:
    """对已提取文本执行敏感信息处理和 LLM 结构化语义分析。

    本服务不负责源文件读取、文件格式提取或对象存储写入。
    """

    def __init__(
        self,
        generator: StructuredJsonGenerator,
        *,
        max_semantic_input_bytes: int,
    ) -> None:
        self.generator = generator
        self._max_semantic_input_bytes = max_semantic_input_bytes

    async def analyze(
        self,
        request: FileSemanticAnalysisRequest,
        extracted_content: ExtractedFileContent,
    ) -> FileSemanticAnalysisResult:
        """结合请求元数据和已提取文本生成结构化文件详情。"""
        extracted_text = extracted_content.get("text", "")
        if len(extracted_text.encode("utf-8")) > self._max_semantic_input_bytes:
            return self._failed(
                request,
                "提取文本超过文件语义分析上限",
                error_code="FILE_DETAIL_SOURCE_TOO_LARGE",
            )
        try:
            sanitized_content = sanitize_sensitive_content(extracted_text)
        except SensitiveContentBlockedError:
            return self._failed(
                request,
                "文件包含私钥内容，已阻止发送至模型",
                error_code="FILE_DETAIL_SENSITIVE_CONTENT_BLOCKED",
            )
        metadata = {
            "project_id": str(request.project_id),
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
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
        prompt = (
            f"{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value}"
            f"\n\n# 文件元数据\n{metadata_json}"
            f"\n\n# 待分析文件内容\n<source_file>\n{sanitized_content.text}\n</source_file>"
            f"\n\n{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL_FINAL_CHECK.value}"
        )
        try:
            semantic_output = await self.generator.generate(
                prompt,
                FileDetailSemanticOutput,
            )
        except (ValidationError, ValueError):
            logger.warning(
                "文件语义分析模型输出无效 action=project_file.semantic.analyze "
                "projectId=%s fileId=%s",
                request.project_id,
                request.file_id,
            )
            return FileSemanticAnalysisResult(
                project_id=request.project_id,
                file_id=request.file_id,
                content_hash=request.content_hash,
                status="failed",
                error_code="FILE_DETAIL_MODEL_OUTPUT_INVALID",
                error_message="模型返回的文件详情格式不正确",
            )
        except Exception:
            logger.exception(
                "文件语义分析模型调用失败 action=project_file.semantic.analyze "
                "projectId=%s fileId=%s",
                request.project_id,
                request.file_id,
            )
            return self._failed(request, "文件语义分析失败")

        now = datetime.now()
        semantic_fields = semantic_output.model_dump()
        semantic_fields["sensitive_flags"] = [
            *sanitized_content.flags,
            *semantic_output.sensitive_flags,
        ]
        detail = FileDetail(
            id=f"file-{request.file_id}",
            project_id=request.project_id,
            file_id=request.file_id,
            schema_version="2.0.0",
            generated_at=now,
            updated_at=now,
            storage_uuid=request.storage_uuid,
            storage_name=request.storage_name,
            detail_ref=request.detail_ref,
            original_path=request.original_path,
            minio_path=request.minio_path,
            size_bytes=request.size_bytes,
            content_type=request.content_type,
            content_hash=request.content_hash,
            status="active",
            previous_versions=[],
            **semantic_fields,
        )

        return FileSemanticAnalysisResult(
            project_id=request.project_id,
            file_id=request.file_id,
            content_hash=request.content_hash,
            status="success",
            detail=detail,
        )

    @staticmethod
    def _failed(
        request: FileSemanticAnalysisRequest,
        message: str,
        *,
        error_code: str = "FILE_DETAIL_ANALYSIS_FAILED",
    ) -> FileSemanticAnalysisResult:
        return FileSemanticAnalysisResult(
            project_id=request.project_id,
            file_id=request.file_id,
            content_hash=request.content_hash,
            status="failed",
            error_code=error_code,
            error_message=message,
        )
