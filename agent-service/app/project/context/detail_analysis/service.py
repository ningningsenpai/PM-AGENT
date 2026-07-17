"""文件下载、完整详情解析和 Java 回调编排。"""
from __future__ import annotations

import hashlib

import httpx
from pydantic import ValidationError

from app.project.context.detail_analysis.enricher import FileDetailModelEnricher
from app.project.context.detail_analysis.parser import FileDetailParser
from app.project.context.detail_analysis.schemas import FileAnalysisResult, FileDetailDocument, FileParsingEvent
from app.project.context.detail_analysis.settings import FileDetailAnalysisSettings


class FileDetailAnalysisService:
    def __init__(
        self,
        settings: FileDetailAnalysisSettings,
        parser: FileDetailParser | None = None,
    ) -> None:
        self._settings = settings
        self._parser = parser or FileDetailParser()
        self._enricher = FileDetailModelEnricher() if settings.llm_enabled else None

    async def process(self, event: FileParsingEvent) -> None:
        """无论解析成功或失败都回调 Java；只有 Java 确认后调用方才可确认 MQ。"""
        try:
            content = await self._download(event)
            self._verify_hash(event, content)
            text = self._decode(content)
            existing_detail = await self._download_existing_detail(event)
            detail = self._parser.parse(event, text, existing_detail)
            if self._enricher is not None:
                detail = await self._enricher.enrich(event, text, detail)
            result = FileAnalysisResult(
                event_id=event.event_id,
                batch_id=event.batch_id,
                content_hash=event.content_hash,
                analysis_version=event.analysis_version,
                status="success",
                detail=detail,
            )
        except Exception as exception:
            result = FileAnalysisResult(
                event_id=event.event_id,
                batch_id=event.batch_id,
                content_hash=event.content_hash,
                analysis_version=event.analysis_version,
                status="failed",
                error_code=self._error_code(exception),
                error_message=self._safe_error_message(exception),
            )
        await self._callback(event, result)

    async def _download(self, event: FileParsingEvent) -> bytes:
        source_url = event.source_url
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            response = await client.get(source_url, headers={"X-Trace-Id": event.trace_id})
            if response.status_code in {401, 403}:
                source_url = await self._refresh_read_url(client, event)
                response = await client.get(source_url, headers={"X-Trace-Id": event.trace_id})
            response.raise_for_status()
            content = response.content
        if len(content) > self._settings.max_source_bytes:
            raise ValueError("源文件大小超过详情解析上限")
        return content

    async def _refresh_read_url(
        self,
        client: httpx.AsyncClient,
        event: FileParsingEvent,
    ) -> str:
        response = await client.get(
            event.read_url_refresh_url,
            headers={
                "X-Internal-Service-Token": self._settings.internal_token,
                "X-Trace-Id": event.trace_id,
            },
        )
        response.raise_for_status()
        body = response.json()
        source_url = (body.get("data") or {}).get("sourceUrl")
        if not source_url:
            raise RuntimeError("Java 未返回新的文件只读地址")
        return str(source_url)

    async def _download_existing_detail(
        self,
        event: FileParsingEvent,
    ) -> FileDetailDocument | None:
        if not event.existing_detail_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
                response = await client.get(
                    event.existing_detail_url,
                    headers={"X-Trace-Id": event.trace_id},
                )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return FileDetailDocument.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError, ValueError):
            return None

    def _verify_hash(self, event: FileParsingEvent, content: bytes) -> None:
        actual_hash = "sha256:" + hashlib.sha256(content).hexdigest()
        if actual_hash.lower() != event.content_hash.lower():
            raise ValueError("下载内容哈希与消息中的 content_hash 不一致")

    def _decode(self, content: bytes) -> str:
        if b"\x00" in content[:4096]:
            raise ValueError("当前详情解析器不支持二进制文件")
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    async def _callback(self, event: FileParsingEvent, result: FileAnalysisResult) -> None:
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            response = await client.put(
                event.callback_url,
                json=payload,
                headers={
                    "X-Internal-Service-Token": self._settings.internal_token,
                    "X-Idempotency-Key": event.event_id,
                    "X-Trace-Id": event.trace_id,
                },
            )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(f"Java 拒绝文件解析结果：{body.get('message') or '未知错误'}")

    def _error_code(self, exception: Exception) -> str:
        if isinstance(exception, httpx.HTTPError):
            return "FILE_SOURCE_READ_FAILED"
        if isinstance(exception, ValueError):
            return "FILE_DETAIL_VALIDATION_FAILED"
        return "FILE_DETAIL_PARSE_FAILED"

    def _safe_error_message(self, exception: Exception) -> str:
        if isinstance(exception, ValidationError):
            return "文件详情结构校验失败"
        if isinstance(exception, httpx.HTTPError):
            return "读取待解析文件失败"
        message = str(exception).strip() or "文件详情解析失败"
        return message[:500]
