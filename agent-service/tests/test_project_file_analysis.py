"""项目文件同步解析接口与服务测试。"""

from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock
from app.project.context.detail_analysis.schemas import (
    FileAnalysisRequest,
    FileAnalysisResult,
    FileDetail,
)
from app.project.context.detail_analysis.service import FileDetailAnalysisService
from app.project.context.model.schemas import ProjectContextModelResponse

_TRACE_ID = "trace-file-analysis-1"


def _request() -> FileAnalysisRequest:
    return FileAnalysisRequest(
        user_id=1,
        project_id=10,
        business="project",
        file_id=30,
        filename="README.md",
        file_url="http://minio/source",
        file_type="markdown",
        storage_uuid="a1b2c3d4e5f67890",
        storage_name="README-a1b2c3d4e5f67890.md",
        detail_ref="system/file_details/README-a1b2c3d4e5f67890.json",
        original_path="docs/README.md",
        minio_path="project/README-a1b2c3d4e5f67890.md",
        size_bytes=1024,
        content_type="text/markdown",
        content_hash="sha256:0123456789abcdef",
        analysis_version="file-detail-v1",
    )


def _detail_data(request: FileAnalysisRequest) -> dict:
    return {
        "id": f"file-{request.file_id}",
        "project_id": request.project_id,
        "file_id": request.file_id,
        "schema_version": "1.0.0",
        "analysis_version": request.analysis_version,
        "generated_at": "2026-07-22T10:00:00",
        "updated_at": "2026-07-22T10:00:00",
        "storage_uuid": request.storage_uuid,
        "storage_name": request.storage_name,
        "detail_ref": request.detail_ref,
        "original_path": request.original_path,
        "minio_path": request.minio_path,
        "size_bytes": request.size_bytes,
        "content_type": request.content_type,
        "content_hash": request.content_hash,
        "module": "docs",
        "kind": "documentation",
        "file_type": "doc",
        "language": "markdown",
        "status": "active",
        "importance": "medium",
        "summary": "项目说明",
        "keywords": ["项目文件"],
        "role": "说明项目结构",
        "content_slices": [],
        "related_topics": [],
        "related_files": [],
        "risk_flags": [],
        "sensitive_flags": [],
        "evidence": [],
        "previous_versions": [],
        "parser": {"strategy": "llm_enhanced"},
    }


def _model_response(content: str) -> ProjectContextModelResponse:
    return ProjectContextModelResponse(
        provider="ollama",
        model="test-model",
        content=content,
        done=True,
        finish_reason="stop",
        latency_ms=1,
        prompt_tokens=10,
        completion_tokens=1,
    )


class FileDetailAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_analyze_should_return_structured_detail(self) -> None:
        request = _request()
        service = FileDetailAnalysisService.__new__(FileDetailAnalysisService)
        service.file_content = Mock()
        service.file_content.get_content = AsyncMock(
            return_value={"content": "# 项目说明"}
        )
        service.client = Mock()
        service.client.generate.return_value = _model_response(
            json.dumps(_detail_data(request), ensure_ascii=False)
        )

        result = await service.analyze(request)

        self.assertEqual("success", result.status)
        self.assertEqual(request.file_id, result.file_id)
        self.assertIsNotNone(result.detail)
        self.assertEqual("markdown", result.detail.language)

    async def test_analyze_should_return_failure_for_invalid_model_output(self) -> None:
        request = _request()
        service = FileDetailAnalysisService.__new__(FileDetailAnalysisService)
        service.file_content = Mock()
        service.file_content.get_content = AsyncMock(
            return_value={"content": "# 项目说明"}
        )
        service.client = Mock()
        service.client.generate.return_value = _model_response("这不是合法 JSON")

        result = await service.analyze(request)

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_MODEL_OUTPUT_INVALID", result.error_code)
        self.assertIsNone(result.detail)

    async def test_analyze_should_return_failure_when_download_fails(self) -> None:
        request = _request()
        service = FileDetailAnalysisService.__new__(FileDetailAnalysisService)
        service.file_content = Mock()
        service.file_content.get_content = AsyncMock(
            side_effect=RuntimeError("下载失败")
        )
        service.client = Mock()

        result = await service.analyze(request)

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_ANALYSIS_FAILED", result.error_code)
        self.assertIsNone(result.detail)
