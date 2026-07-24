"""项目文件状态机与外部调用边界测试。"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.core.config import FileConfig, StorageConfig
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project_file.domain import ProjectFileStatus
from app.modules.project_file.models import ProjectFile
from app.modules.project_file.service import ProjectFileService


def _file_config() -> FileConfig:
    return FileConfig(
        max_size_bytes=1024,
        ignored_directories=frozenset(),
        ignored_file_names=frozenset(),
        blocked_extensions=frozenset(),
        blocked_mime_types=frozenset(),
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


def _service(repository, storage) -> ProjectFileService:
    projects = AsyncMock()
    projects.require_owned.return_value = SimpleNamespace(
        id=10,
        owner_user_id=1,
    )
    return ProjectFileService(
        repository,
        projects,
        storage,
        StorageLocationFactory(_storage_config()),
        AsyncMock(),
        AsyncMock(),
        _file_config(),
        _storage_config(),
    )


class ProjectFileStateMachineTest(IsolatedAsyncioTestCase):
    async def test_upload_failure_should_keep_diagnosable_database_state(
        self,
    ) -> None:
        session = AsyncMock()
        repository = SimpleNamespace(
            session=session,
            find_path=AsyncMock(return_value=None),
            add=AsyncMock(),
        )

        async def assign_id(file: ProjectFile) -> ProjectFile:
            file.id = 30
            file.created_at = datetime.now()
            file.updated_at = datetime.now()
            return file

        repository.add.side_effect = assign_id
        storage = Mock()
        storage.put_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        service = _service(repository, storage)

        result = await service.upload(
            user_id=1,
            project_id=10,
            idempotency_key="upload-1",
            relative_path="docs/README.md",
            source_mtime_ms=100,
            content=b"# README",
            supplied_content_type="text/markdown",
        )

        file = repository.add.await_args.args[0]
        self.assertFalse(result.success)
        self.assertEqual("upload_failed", result.status)
        self.assertEqual("failed", result.upload_status)
        self.assertEqual("FILE_STORAGE_ERROR", file.last_error_code)
        self.assertIsNotNone(file.last_failed_at)
        self.assertEqual(2, session.commit.await_count)

    async def test_concurrent_state_claim_should_be_rejected(self) -> None:
        repository = SimpleNamespace(
            session=SimpleNamespace(
                rollback=AsyncMock(),
                commit=AsyncMock(),
                refresh=AsyncMock(),
            ),
            claim_state=AsyncMock(return_value=False),
        )
        service = _service(repository, Mock())
        file = ProjectFile(
            id=30,
            project_id=10,
            business_code="project",
            relative_path="README.md",
            path_hash="a" * 64,
            file_name="README.md",
            extension="md",
            storage_uuid="a1b2c3d4e5f67890",
            storage_name="README-a1b2c3d4e5f67890.md",
            object_key="PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
            minio_path="project/README-a1b2c3d4e5f67890.md",
            content_type="text/markdown",
            size_bytes=10,
            source_mtime_ms=0,
            quick_fingerprint="b" * 64,
            content_hash="c" * 64,
            status="active",
            upload_status="success",
            upload_attempts=1,
            parse_attempts=0,
            lock_version=2,
        )

        with self.assertRaises(AppException) as caught:
            await service._claim_state(
                file,
                2,
                ProjectFileStatus.UPDATING,
            )

        self.assertIs(ErrorCode.FILE_BUSY, caught.exception.error)
        repository.session.rollback.assert_awaited_once()
