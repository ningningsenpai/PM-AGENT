"""项目文件同步解析接口与服务测试。"""
from __future__ import annotations

import hashlib
from datetime import datetime
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.project.context.detail_analysis.parser import FileDetailParser
from app.project.context.detail_analysis.schemas import FileAnalysisRequest, FileAnalysisResult
from app.project.context.detail_analysis.file_content import FileDetailAnalysisService
from app.project.context.detail_analysis.settings import FileDetailAnalysisSettings

_INTERNAL_TOKEN = "test-internal-token"
_TRACE_ID = "trace-file-analysis-1"


def _settings() -> FileDetailAnalysisSettings:
    return FileDetailAnalysisSettings(
        internal_token=_INTERNAL_TOKEN,
        request_timeout_seconds=5,
        max_source_bytes=1024 * 1024,
        llm_enabled=False,
    )


def _request(content: str = "# 项目说明\n") -> FileAnalysisRequest:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return FileAnalysisRequest(
        project_id=10,
        file_id=30,
        storage_uuid="a1b2c3d4e5f67890",
        storage_name="README-a1b2c3d4e5f67890.md",
        logical_path="docs/README.md",
        minio_path="project/README-a1b2c3d4e5f67890.md",
        size_bytes=len(content.encode("utf-8")),
        content_type="text/markdown",
        content_hash=f"sha256:{digest}",
        source_url="http://minio/source",
        existing_detail_url=None,
        detail_ref="system/file_details/README-a1b2c3d4e5f67890.json",
        analysis_version="file-detail-v1",
        occurred_at=datetime(2026, 7, 21, 10, 0),
    )


class FileDetailAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_analyze_should_return_structured_detail(self) -> None:
        content = "# 项目说明\n"
        request = _request(content)
        service = FileDetailAnalysisService(_settings())

        with patch.object(service, "_download", AsyncMock(return_value=content.encode("utf-8"))):
            result = await service.analyze(request, _TRACE_ID)

        self.assertEqual("success", result.status)
        self.assertEqual(request.file_id, result.file_id)
        self.assertIsNotNone(result.detail)
        self.assertEqual("markdown", result.detail.language)

    async def test_analyze_should_return_failure_when_hash_mismatches(self) -> None:
        request = _request("# 原始内容\n")
        service = FileDetailAnalysisService(_settings())

        with patch.object(service, "_download", AsyncMock(return_value=b"changed")):
            result = await service.analyze(request, _TRACE_ID)

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_VALIDATION_FAILED", result.error_code)
        self.assertIsNone(result.detail)


def test_analyze_api_should_return_camel_case_result() -> None:
    request = _request()
    detail = FileDetailParser().parse(request, "# 项目说明\n")
    result = FileAnalysisResult(
        project_id=request.project_id,
        file_id=request.file_id,
        content_hash=request.content_hash,
        analysis_version=request.analysis_version,
        status="success",
        detail=detail,
    )

    with (
        patch("app.api.v1.project_files.get_file_detail_analysis_settings", return_value=_settings()),
        patch(
            "app.api.v1.project_files.FileDetailAnalysisService.analyze",
            AsyncMock(return_value=result),
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/project-files/analyze",
            json=request.model_dump(mode="json", by_alias=True),
            headers={
                "X-Internal-Service-Token": _INTERNAL_TOKEN,
                "X-Trace-Id": _TRACE_ID,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["projectId"] == request.project_id
    assert body["detail"]["contentHash"] == request.content_hash


def test_analyze_api_should_reject_invalid_internal_token() -> None:
    with patch("app.api.v1.project_files.get_file_detail_analysis_settings", return_value=_settings()):
        response = TestClient(app).post(
            "/api/v1/project-files/analyze",
            json=_request().model_dump(mode="json", by_alias=True),
            headers={
                "X-Internal-Service-Token": "invalid-token",
                "X-Trace-Id": _TRACE_ID,
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "内部服务令牌无效"
