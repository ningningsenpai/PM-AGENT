"""项目上下文索引服务单元测试。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

import app.project_context.index as index_package
from app.core.config import StorageConfig
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.project_context.index import ProjectIndexDocument, ProjectIndexService
from app.project_context.index.schemas import (
    ProjectIndexDocument as SchemaProjectIndexDocument,
)
from app.project_context.index.service import (
    ProjectIndexService as ServiceProjectIndexService,
)


def _storage_config() -> StorageConfig:
    return StorageConfig(
        endpoint="127.0.0.1:9000",
        access_key="test",
        secret_key="test",
        secure=False,
        bucket="pm-agent-test",
        read_url_expiry_seconds=300,
    )


def _project():
    return SimpleNamespace(
        id=12,
        owner_user_id=7,
        project_name="PM-Agent",
        created_at=datetime(2026, 7, 27, 9, 0, 0),
    )


def _file(
    *,
    file_id: int,
    business_code: str = "project",
    status: str = "active",
    upload_status: str = "success",
    detail_ref: str | None = "system/file_details/detail.json",
):
    return SimpleNamespace(
        id=file_id,
        business_code=business_code,
        relative_path=f"docs/{file_id}.md",
        file_name=f"{file_id}.md",
        storage_uuid=f"uuid{file_id:012d}"[-16:],
        storage_name=f"{file_id}-stored.md",
        minio_path=f"project/{file_id}-stored.md",
        size_bytes=100,
        content_type="text/markdown",
        status=status,
        upload_status=upload_status,
        quick_fingerprint="a" * 64,
        content_hash="b" * 64,
        updated_at=datetime(2026, 7, 27, 10, 0, 0),
        upload_attempts=2,
        last_error_code="FILE_STORAGE_ERROR",
        detail_ref=detail_ref,
        module="docs",
        kind="documentation",
        file_type="doc",
        language="markdown",
        importance="medium",
        summary="项目说明",
        keywords=["项目"],
    )


class ProjectIndexServiceTest(IsolatedAsyncioTestCase):
    def test_build_classifies_active_and_failed_files(self) -> None:
        """验证索引快照会分类有效文件并汇总失败记录。

        @Param project: 包含项目标识和创建时间的项目对象。
        @Param files: 包含 project、user、失败和非活跃状态的文件集合。
        @Return: 分类、分析投影和统计字段完整的索引文档。
        """
        service = ProjectIndexService(
            Mock(),
            StorageLocationFactory(_storage_config()),
        )
        files = [
            _file(file_id=1),
            _file(file_id=2, business_code="user"),
            _file(
                file_id=3,
                status="upload_failed",
                upload_status="failed",
            ),
            _file(
                file_id=4,
                status="uploading",
                upload_status="not_uploaded",
            ),
        ]

        document = service.build(_project(), files)

        self.assertIsInstance(document, ProjectIndexDocument)
        self.assertEqual(4, document.summary.total_nodes)
        self.assertEqual(2, document.summary.active_files)
        self.assertEqual(2, document.summary.fail_nodes)
        self.assertEqual([1], [item.id for item in document.project])
        self.assertEqual([2], [item.id for item in document.user])
        self.assertEqual("docs", document.project[0].module)
        self.assertEqual(
            {"upload_failed", "not_uploaded"},
            {item.status for item in document.upload_failures},
        )

    async def test_write_serializes_complete_snapshot(self) -> None:
        """验证索引写入会生成完整 JSON 快照。

        @Param project: 待生成索引的项目对象。
        @Param files: 当前数据库中的文件集合。
        @Return: None，操作成功完成。
        @SideEffect: 向项目 system/index.json 写入 UTF-8 JSON。
        """
        storage = Mock()
        service = ProjectIndexService(
            storage,
            StorageLocationFactory(_storage_config()),
        )

        await service.write(_project(), [_file(file_id=1)])

        location, content, content_type = storage.put_bytes.call_args.args
        payload = json.loads(content.decode("utf-8"))
        self.assertEqual("pm-agent-test", location.bucket)
        self.assertTrue(location.object_key.endswith("/system/index.json"))
        self.assertEqual("application/json", content_type)
        self.assertIn(b'\n  "project_id"', content)
        self.assertIn("项目说明".encode(), content)
        self.assertEqual(1, payload["summary"]["total_nodes"])

    async def test_write_wraps_storage_failure(self) -> None:
        """验证索引存储失败会转换为项目索引业务异常。

        @Param project: 待生成索引的项目对象。
        @Param files: 当前数据库中的文件集合。
        @Return: 抛出 PROJECT_INDEX_WRITE_FAILED 的 AppException。
        """
        storage = Mock()
        storage.put_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        service = ProjectIndexService(
            storage,
            StorageLocationFactory(_storage_config()),
        )

        with self.assertRaises(AppException) as caught:
            await service.write(_project(), [])

        self.assertIs(ErrorCode.PROJECT_INDEX_WRITE_FAILED, caught.exception.error)

    async def test_initialize_writes_empty_snapshot(self) -> None:
        storage = Mock()
        service = ProjectIndexService(
            storage,
            StorageLocationFactory(_storage_config()),
        )

        await service.initialize(_project())

        location, content, content_type = storage.put_bytes.call_args.args
        payload = json.loads(content.decode("utf-8"))
        self.assertTrue(location.object_key.endswith("/system/index.json"))
        self.assertEqual("application/json", content_type)
        self.assertEqual([], payload["project"])
        self.assertEqual([], payload["user"])
        self.assertEqual([], payload["upload_failures"])
        self.assertEqual(
            {"total_nodes": 0, "active_files": 0, "fail_nodes": 0},
            payload["summary"],
        )

    def test_build_preserves_detail_ref(self) -> None:
        service = ProjectIndexService(
            Mock(),
            StorageLocationFactory(_storage_config()),
        )

        document = service.build(
            _project(),
            [
                _file(
                    file_id=1,
                    detail_ref="system/file_details/stale.json",
                )
            ],
        )

        self.assertEqual(
            "system/file_details/stale.json",
            document.project[0].detail_ref,
        )

    def test_package_exports_only_public_document_and_service(self) -> None:
        self.assertIs(ProjectIndexDocument, SchemaProjectIndexDocument)
        self.assertIs(ProjectIndexService, ServiceProjectIndexService)
        self.assertIs(index_package.ProjectIndexDocument, ProjectIndexDocument)
        self.assertIs(index_package.ProjectIndexService, ProjectIndexService)
        self.assertEqual(
            {"ProjectIndexDocument", "ProjectIndexService"},
            set(index_package.__all__),
        )

    def test_document_serialization_keeps_existing_json_contract(self) -> None:
        service = ProjectIndexService(
            Mock(),
            StorageLocationFactory(_storage_config()),
        )

        payload = service.build(
            _project(),
            [
                _file(file_id=2, business_code="user"),
                _file(file_id=1),
                _file(
                    file_id=3,
                    status="upload_failed",
                    upload_status="failed",
                ),
            ],
        ).model_dump(mode="json")

        self.assertEqual(
            [
                "project_id",
                "project_name",
                "owner_user_id",
                "schema_version",
                "generated_at",
                "updated_at",
                "storage",
                "summary",
                "project",
                "user",
                "upload_failures",
                "system",
            ],
            list(payload),
        )
        self.assertEqual(
            [
                "id",
                "storage_uuid",
                "logical_path",
                "file_name",
                "storage_name",
                "minio_path",
                "size_bytes",
                "content_type",
                "status",
                "quick_fingerprint",
                "content_hash",
                "updated_at",
                "detail_ref",
                "module",
                "kind",
                "file_type",
                "language",
                "importance",
                "summary",
                "keywords",
            ],
            list(payload["project"][0]),
        )
        self.assertEqual(
            [
                "provider",
                "bucket",
                "object_prefix",
                "index_path",
            ],
            list(payload["storage"]),
        )
        self.assertEqual(
            ["total_nodes", "active_files", "fail_nodes"],
            list(payload["summary"]),
        )
        self.assertEqual(
            [
                "file_id",
                "business",
                "logical_path",
                "file_name",
                "storage_name",
                "status",
                "attempts",
                "last_error_code",
                "updated_at",
            ],
            list(payload["upload_failures"][0]),
        )
        self.assertEqual(
            [
                "index",
                "project_specification",
                "long_term_memory",
                "short_term_memory",
                "user_habits",
                "update_journal",
            ],
            list(payload["system"]),
        )
        self.assertEqual("2.0.0", payload["schema_version"])
        self.assertEqual("2026-07-27T09:00:00+08:00", payload["generated_at"])
        datetime.fromisoformat(payload["updated_at"])
        self.assertEqual([1], [item["id"] for item in payload["project"]])
        self.assertEqual([2], [item["id"] for item in payload["user"]])
        self.assertEqual(
            f"qf:sha256:{'a' * 64}",
            payload["project"][0]["quick_fingerprint"],
        )
        self.assertEqual(
            f"sha256:{'b' * 64}",
            payload["project"][0]["content_hash"],
        )
        self.assertEqual(
            "2026-07-27T10:00:00+08:00",
            payload["project"][0]["updated_at"],
        )
        self.assertEqual(
            "2026-07-27T10:00:00+08:00",
            payload["upload_failures"][0]["updated_at"],
        )
