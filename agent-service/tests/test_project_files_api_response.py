from __future__ import annotations

from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.project.context.detail_analysis.schemas import FileAnalysisResult, FileDetail


_TRACE_ID = "trace-file-analysis-1"


def _request_body() -> dict:
    return {
        "userId": 1,
        "projectId": 10,
        "business": "project",
        "fileId": 30,
        "filename": "README.md",
        "fileUrl": "http://minio/source",
        "fileType": "markdown",
        "storageUuid": "a1b2c3d4e5f67890",
        "storageName": "README-a1b2c3d4e5f67890.md",
        "detailRef": "system/file_details/README-a1b2c3d4e5f67890.json",
        "originalPath": "docs/README.md",
        "minioPath": "PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
        "sizeBytes": 1024,
        "contentType": "text/markdown",
        "contentHash": "sha256:0123456789abcdef",
        "analysisVersion": "file-detail-v1",
    }


def _detail() -> FileDetail:
    return FileDetail(
        id="file-30",
        project_id=10,
        file_id=30,
        schema_version="1.0.0",
        analysis_version="file-detail-v1",
        generated_at="2026-07-22T10:00:00",
        updated_at="2026-07-22T10:00:00",
        storage_uuid="a1b2c3d4e5f67890",
        storage_name="README-a1b2c3d4e5f67890.md",
        detail_ref="system/file_details/README-a1b2c3d4e5f67890.json",
        original_path="docs/README.md",
        minio_path="PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
        size_bytes=1024,
        content_type="text/markdown",
        content_hash="sha256:0123456789abcdef",
        module="docs",
        kind="documentation",
        file_type="doc",
        language="markdown",
        status="active",
        importance="medium",
        summary="项目说明",
        keywords=["项目文件"],
        role="说明项目结构",
        content_slices=[],
        related_topics=[],
        related_files=[],
        risk_flags=[],
        sensitive_flags=[],
        evidence=[],
        previous_versions=[],
        parser={"strategy": "llm_enhanced"},
    )


class ProjectFilesApiResponseTest(TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_analyze_should_return_structured_success_result(self) -> None:
        service = AsyncMock()
        service.analyze.return_value = FileAnalysisResult(
            project_id=10,
            file_id=30,
            content_hash="sha256:0123456789abcdef",
            analysis_version="file-detail-v1",
            status="success",
            detail=_detail(),
        )

        with patch(
            "app.api.v1.project_files.FileDetailAnalysisService",
            return_value=service,
        ):
            response = self.client.post(
                "/api/v1/project-files/analyze",
                json=[_request_body()],
                headers={"X-Trace-Id": _TRACE_ID},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("success", response.json()[0]["status"])
        self.assertEqual("file-30", response.json()[0]["detail"]["id"])
        self.assertEqual("docs", response.json()[0]["detail"]["module"])
        self.assertEqual(
            "system/file_details/README-a1b2c3d4e5f67890.json",
            response.json()[0]["detail"]["detail_ref"],
        )

    def test_analyze_should_return_failed_result_for_plain_text(self) -> None:
        service = AsyncMock()
        service.analyze.return_value = FileAnalysisResult(
            project_id=10,
            file_id=30,
            content_hash="sha256:0123456789abcdef",
            analysis_version="file-detail-v1",
            status="failed",
            error_code="FILE_DETAIL_MODEL_OUTPUT_INVALID",
            error_message="模型返回的文件详情格式不正确",
        )

        with patch(
            "app.api.v1.project_files.FileDetailAnalysisService",
            return_value=service,
        ):
            response = self.client.post(
                "/api/v1/project-files/analyze",
                json=[_request_body()],
                headers={"X-Trace-Id": _TRACE_ID},
            )

        body = response.json()[0]
        self.assertEqual(200, response.status_code)
        self.assertEqual("failed", body["status"])
        self.assertEqual("FILE_DETAIL_MODEL_OUTPUT_INVALID", body["errorCode"])
        self.assertIsNone(body["detail"])
