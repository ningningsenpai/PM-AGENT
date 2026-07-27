"""项目索引服务单元测试。"""

from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from app.core.config import StorageConfig
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project.index_service import ProjectIndexService


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
        detail_ref="system/file_details/detail.json",
        analysis_version="file-detail-v1",
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
        @Return: 分类、分析投影和统计字段完整的索引字典。
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

        payload = service.build(_project(), files)

        self.assertEqual(4, payload["summary"]["total_nodes"])
        self.assertEqual(2, payload["summary"]["active_files"])
        self.assertEqual(2, payload["summary"]["fail_nodes"])
        self.assertEqual([1], [item["id"] for item in payload["project"]])
        self.assertEqual([2], [item["id"] for item in payload["user"]])
        self.assertEqual("docs", payload["project"][0]["module"])
        self.assertEqual(
            {"upload_failed", "not_uploaded"},
            {item["status"] for item in payload["upload_failures"]},
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
