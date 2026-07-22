from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.project.context.detail_analysis.schemas import FileAnalysisRequest
from app.project.context.detail_analysis.service import FileDetailAnalysisService
from app.project.context.model.schemas import ProjectContextModelResponse


class FileDetailAnalysisMetadataTest(IsolatedAsyncioTestCase):
    async def test_analyze_should_include_stable_metadata_in_prompt(self) -> None:
        request = FileAnalysisRequest(
            user_id=1,
            project_id=10,
            business="project",
            file_id=30,
            filename="README.md",
            file_url="http://minio/source?temporary-token=secret",
            file_type="markdown",
            storage_uuid="a1b2c3d4e5f67890",
            storage_name="README-a1b2c3d4e5f67890.md",
            detail_ref="system/file_details/README-a1b2c3d4e5f67890.json",
            original_path="docs/README.md",
            minio_path="PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
            size_bytes=1024,
            content_type="text/markdown",
            content_hash="sha256:0123456789abcdef",
            analysis_version="file-detail-v1",
        )
        model_response = ProjectContextModelResponse(
            provider="ollama",
            model="test-model",
            content=json.dumps(
                {
                    "id": "file-30",
                    "project_id": 10,
                    "file_id": 30,
                    "schema_version": "1.0.0",
                    "analysis_version": "file-detail-v1",
                    "generated_at": "2026-07-22T10:00:00",
                    "updated_at": "2026-07-22T10:00:00",
                    "storage_uuid": "a1b2c3d4e5f67890",
                    "storage_name": "README-a1b2c3d4e5f67890.md",
                    "detail_ref": "system/file_details/README-a1b2c3d4e5f67890.json",
                    "original_path": "docs/README.md",
                    "minio_path": "PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
                    "size_bytes": 1024,
                    "content_type": "text/markdown",
                    "content_hash": "sha256:0123456789abcdef",
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
                },
                ensure_ascii=False,
            ),
            done=True,
            finish_reason="stop",
            latency_ms=1,
            prompt_tokens=10,
            completion_tokens=1,
        )
        service = FileDetailAnalysisService.__new__(FileDetailAnalysisService)
        service.file_content = Mock()
        service.file_content.get_content = AsyncMock(
            return_value={"type": "markdown", "content": "# 项目说明"}
        )
        service.client = Mock()
        service.client.generate.return_value = model_response

        result = await service.analyze(request)

        service.file_content.get_content.assert_awaited_once_with(
            request.file_url,
            request.file_type,
        )
        prompt = service.client.generate.call_args.args[0]
        self.assertEqual(
            "json",
            service.client.generate.call_args.kwargs["response_format"],
        )
        metadata_text = prompt.split("# 文件元数据\n", maxsplit=1)[1].split(
            "\n\n# 待分析文件内容",
            maxsplit=1,
        )[0]
        metadata = json.loads(metadata_text)

        self.assertEqual(request.project_id, metadata["project_id"])
        self.assertEqual(request.file_id, metadata["file_id"])
        self.assertEqual(request.storage_uuid, metadata["storage_uuid"])
        self.assertEqual(request.storage_name, metadata["storage_name"])
        self.assertEqual(request.content_hash, metadata["content_hash"])
        self.assertEqual(request.analysis_version, metadata["analysis_version"])
        self.assertEqual(request.detail_ref, metadata["detail_ref"])
        self.assertEqual(request.minio_path, metadata["minio_path"])
        self.assertNotIn("file_url", metadata)
        self.assertNotIn("user_id", metadata)
        self.assertIn("# 项目说明", prompt)
        self.assertIn("<source_file>\n# 项目说明\n</source_file>", prompt)
        self.assertIn("# 最终输出检查", prompt)
        self.assertGreater(
            prompt.rfind("# 最终输出检查"),
            prompt.rfind("# 项目说明"),
        )
        self.assertIn("禁止输出空字符串字段名", prompt)
        self.assertEqual("success", result.status)
        self.assertIsNotNone(result.detail)
        self.assertEqual("docs", result.detail.module)

        request_body = request.model_dump(by_alias=True)
        self.assertEqual(request.project_id, request_body["projectId"])
        self.assertEqual(request.storage_uuid, request_body["storageUuid"])
        self.assertNotIn("project_id", request_body)
