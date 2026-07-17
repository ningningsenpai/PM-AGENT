"""完整文件详情解析测试。"""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime

from app.project.context.detail_analysis.parser import FileDetailParser
from app.project.context.detail_analysis.schemas import FileParsingEvent


class FileDetailParserTest(unittest.TestCase):
    def test_markdown_should_keep_projection_and_full_detail_fields(self) -> None:
        content = "# 后端说明\n\n## MinIO 存储\n详情文件由 Java 统一上传。\n"
        event = self._event("backend/README.md", content, "text/markdown")

        detail = FileDetailParser().parse(event, content)

        self.assertEqual("backend", detail.module)
        self.assertEqual("documentation", detail.kind)
        self.assertEqual("markdown", detail.language)
        self.assertTrue(detail.summary)
        self.assertTrue(detail.keywords)
        self.assertTrue(detail.role)
        self.assertTrue(detail.content_slices)
        self.assertEqual("system/file_details/README-a1b2c3d4e5f67890.md", detail.detail_ref)
        self.assertEqual(event.content_hash, detail.content_hash)
        self.assertEqual("deterministic_structure", detail.parser.strategy)

    def test_sensitive_source_should_not_keep_content_slices_or_evidence(self) -> None:
        content = 'api_key = "secret-value-123456"\nclass Client:\n    pass\n'
        event = self._event("agent-service/app/client.py", content, "text/x-python")

        detail = FileDetailParser().parse(event, content)

        self.assertIn("hardcoded_secret_candidate", detail.sensitive_flags)
        self.assertEqual([], detail.content_slices)
        self.assertEqual([], detail.evidence)

    def test_java_source_should_extract_entities_and_source_ranges(self) -> None:
        content = (
            "package demo;\n"
            "public class ProjectFileController {\n"
            "  public void upload() {}\n"
            "}\n"
        )
        event = self._event("backend/src/ProjectFileController.java", content, "text/x-java-source")

        detail = FileDetailParser().parse(event, content)

        self.assertEqual("api", detail.kind)
        self.assertIn("ProjectFileController", detail.keywords)
        self.assertGreaterEqual(len(detail.content_slices), 1)
        self.assertGreaterEqual(detail.content_slices[0].source_range.start_line, 1)

    def test_changed_file_should_keep_previous_version_summary(self) -> None:
        original = "# 旧说明\n"
        original_event = self._event("docs/README.md", original, "text/markdown")
        parser = FileDetailParser()
        old_detail = parser.parse(original_event, original)
        changed = "# 新说明\n"
        changed_event = self._event("docs/README.md", changed, "text/markdown")

        detail = parser.parse(changed_event, changed, old_detail)

        self.assertEqual(1, len(detail.previous_versions))
        self.assertEqual(old_detail.content_hash, detail.previous_versions[0].content_hash)
        self.assertEqual(old_detail.role, detail.previous_versions[0].role)

    def _event(self, logical_path: str, content: str, content_type: str) -> FileParsingEvent:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        file_name = logical_path.rsplit("/", 1)[-1]
        stem, dot, suffix = file_name.rpartition(".")
        storage_name = (
            f"{stem}-a1b2c3d4e5f67890.{suffix}"
            if dot
            else f"{file_name}-a1b2c3d4e5f67890"
        )
        return FileParsingEvent(
            event_id="event-1",
            batch_id=100,
            project_id=10,
            file_id=30,
            storage_uuid="a1b2c3d4e5f67890",
            storage_name=storage_name,
            logical_path=logical_path,
            minio_path=f"project/{storage_name}",
            size_bytes=len(content.encode("utf-8")),
            content_type=content_type,
            content_hash=f"sha256:{digest}",
            source_url="http://minio/source",
            read_url_refresh_url="http://backend/read-url",
            existing_detail_url=None,
            detail_ref=f"system/file_details/{storage_name}",
            analysis_version="file-detail-v1",
            callback_url="http://backend/analysis-result",
            trace_id="trace-1",
            occurred_at=datetime(2026, 7, 16, 10, 10),
        )


if __name__ == "__main__":
    unittest.main()
