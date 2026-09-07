"""文件语义分析服务。"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import ValidationError

from app.core.logger import get_logger
from app.llm.prompts.project_context import ProjectFileDetailPrompt
from app.llm.structured import (
    StructuredJsonGenerator,
    StructuredOutputError,
    StructuredOutputValidationError,
)
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
        numbered_source = "\n".join(
            f"{index}: {line}"
            for index, line in enumerate(sanitized_content.text.splitlines(), 1)
        )
        prompt = (
            f"{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value}"
            f"\n\n# 文件元数据\n{metadata_json}"
            f"\n\n# 待分析文件内容（行号由服务端生成）\n<source_file>\n{numbered_source}\n</source_file>"
            "\ncontent_slices 每项增加 source_quote，必须摘取一段连续原文（不含行号前缀），用于服务端定位；无法摘取则空字符串。"
            "\n增加 project_facts 数组：保存明确的已完成能力、尚未实现能力、阶段、日期、自报进度，每项包含 kind、statement、source_quote。"
            "这些项目事实不是规范规则，不放入 rule_candidates；例如只存在列表和新增接口不能推断为完整 CRUD。"
            f"\n\n{ProjectFileDetailPrompt.PROJECT_FILE_DETAIL_FINAL_CHECK.value}"
        )
        try:
            for attempt in range(2):
                try:
                    semantic_output = await self.generator.generate(
                        prompt, FileDetailSemanticOutput
                    )
                    break
                except StructuredOutputValidationError as exception:
                    if attempt:
                        raise
                    logger.warning(
                        "文件详情字段校验未通过，限定纠正一次 projectId=%s fileId=%s",
                        request.project_id,
                        request.file_id,
                    )
                    prompt += (
                        "\n\n上次输出未通过字段校验。请重新依据相同原文生成完整 JSON，"
                        "补齐必填字段，禁止省略字段或只输出补丁。纠正仅允许一次。\n"
                        + json.dumps(
                            {
                                "validationErrors": exception.errors,
                                "requiredSchema": FileDetailSemanticOutput.model_json_schema(),
                            },
                            ensure_ascii=False,
                        )
                    )
        except (ValidationError, ValueError) as exception:
            message = (
                str(exception)
                if isinstance(exception, StructuredOutputError)
                else "模型返回的文件详情格式不正确"
            )
            logger.warning(
                "文件语义分析模型输出无效 action=project_file.semantic.analyze "
                "projectId=%s fileId=%s reason=%s",
                request.project_id,
                request.file_id,
                message,
            )
            return FileSemanticAnalysisResult(
                project_id=request.project_id,
                file_id=request.file_id,
                content_hash=request.content_hash,
                status="failed",
                error_code="FILE_DETAIL_MODEL_OUTPUT_INVALID",
                error_message=message,
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
        for field in ("content_slices", "project_facts"):
            for item in semantic_fields[field]:
                quote = item.get("source_quote", "")
                index = (
                    sanitized_content.text.find(quote)
                    if isinstance(quote, str) and quote
                    else -1
                )
                # 只接受能唯一定位的原文；未核实的模型行号不继续传播。
                if index >= 0 and sanitized_content.text.find(quote, index + 1) < 0:
                    start = sanitized_content.text[:index].count("\n") + 1
                    item["source_range"] = {
                        "start_line": start,
                        "end_line": start + quote.count("\n"),
                    }
                    item["evidence_verified"] = True
                else:
                    item.pop("source_range", None)
                    item["evidence_verified"] = False
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
