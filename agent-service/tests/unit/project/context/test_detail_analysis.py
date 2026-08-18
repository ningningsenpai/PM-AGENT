"""文件详情分析服务测试。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.project.context.detail_analysis.schemas import FileAnalysisRequest
from app.project.context.detail_analysis.service import FileDetailAnalysisService


def _request() -> FileAnalysisRequest:
    return FileAnalysisRequest(
        user_id=1,
        project_id=10,
        business="project",
        file_id=30,
        filename="README.md",
        file_url="",
        file_type="md",
        storage_uuid="file-uuid",
        storage_name="README-file-uuid.md",
        detail_ref="system/file_details/README-file-uuid.json",
        original_path="README.md",
        minio_path="users/1/projects/10/project/README-file-uuid.md",
        size_bytes=4,
        content_type="text/markdown",
        content_hash="hash",
        analysis_version="file-detail-v1",
    )


class FileDetailAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_analyze_bytes_rejects_source_over_limit_before_model_call(self) -> None:
        generator = SimpleNamespace(generate=AsyncMock())
        service = FileDetailAnalysisService(generator, max_source_bytes=3)
        service.file_content.get_content_from_bytes = AsyncMock(
            return_value={"content": "four"}
        )

        result = await service.analyze_bytes(_request(), b"four")

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_SOURCE_TOO_LARGE", result.error_code)
        generator.generate.assert_not_awaited()

    async def test_analyze_bytes_records_invalid_structured_response(self) -> None:
        generator = SimpleNamespace(
            generate=AsyncMock(side_effect=ValueError("模型输出被截断"))
        )
        service = FileDetailAnalysisService(generator, max_source_bytes=1024)
        service.file_content.get_content_from_bytes = AsyncMock(
            return_value={"content": "project content"}
        )

        result = await service.analyze_bytes(_request(), b"content")

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_MODEL_OUTPUT_INVALID", result.error_code)
