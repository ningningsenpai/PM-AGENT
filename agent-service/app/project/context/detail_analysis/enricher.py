"""使用现有项目上下文模型增强确定性详情基线。"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from app.project.context.detail_analysis.schemas import FileDetailDocument, FileParsingEvent, ParserMetadata
from app.project.context.model.client import ProjectContextModelClient
from app.project.inner_prompts.project_file_detail import ProjectFileDetailPrompt

logger = logging.getLogger(__name__)

_PROTECTED_FIELDS = {
    "id",
    "project_id",
    "file_id",
    "schema_version",
    "analysis_version",
    "generated_at",
    "updated_at",
    "storage_uuid",
    "storage_name",
    "detail_ref",
    "original_path",
    "minio_path",
    "size_bytes",
    "content_type",
    "content_hash",
    "status",
    "previous_versions",
}


class FileDetailModelEnricher:
    def __init__(self, max_content_chars: int = 12_000) -> None:
        self._max_content_chars = max_content_chars

    async def enrich(
        self,
        event: FileParsingEvent,
        text: str,
        baseline: FileDetailDocument,
    ) -> FileDetailDocument:
        """模型输出校验失败时返回确定性基线，避免解析链路因模型不可用而中断。"""
        try:
            prompt = self._build_prompt(event, text, baseline)
            response = await asyncio.to_thread(ProjectContextModelClient().generate, prompt)
            generated = self._parse_json(response.content)
            baseline_data = baseline.model_dump(mode="json")
            for field in _PROTECTED_FIELDS:
                generated[field] = baseline_data[field]
            generated["parser"] = ParserMetadata(
                strategy="llm_enhanced",
                parser_version=f"{baseline.parser.parser_version}+{response.model}",
                sampled=baseline.parser.sampled or len(text) > self._max_content_chars,
                parsed_lines=baseline.parser.parsed_lines,
            ).model_dump(mode="json")
            return FileDetailDocument.model_validate(generated)
        except Exception:
            logger.warning("模型增强文件详情失败，已回退确定性解析，event_id=%s", event.event_id, exc_info=True)
            return baseline

    def _build_prompt(
        self,
        event: FileParsingEvent,
        text: str,
        baseline: FileDetailDocument,
    ) -> str:
        payload = {
            "source_meta": event.model_dump(mode="json", by_alias=True, exclude={"source_url"}),
            "deterministic_baseline": baseline.model_dump(mode="json"),
            "file_content": text[:self._max_content_chars],
        }
        return ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value + "\n\n# 本次输入\n" + json.dumps(
            payload,
            ensure_ascii=False,
        )

    def _parse_json(self, content: str) -> dict:
        normalized = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", normalized, re.DOTALL | re.IGNORECASE)
        if fenced:
            normalized = fenced.group(1)
        value = json.loads(normalized)
        if not isinstance(value, dict):
            raise ValueError("模型详情输出必须是 JSON 对象")
        return value
