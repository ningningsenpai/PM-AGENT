"""项目文件生命周期服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project_file.models import ProjectFile
from app.modules.project_file.management import service as project_file_service_module
from app.modules.project_file.management.schemas import UpdateProjectFilePathRequest
from app.modules.project_file.management.service import ProjectFileService
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)
from tests.unit.modules.project_file.management.factories import file_config


def _repository(file: ProjectFile | None = None, **overrides):
    defaults = {
        "session": SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
            refresh=AsyncMock(),
        ),
        "get": AsyncMock(return_value=file),
        "find_path": AsyncMock(return_value=None),
        "list": AsyncMock(return_value=[]),
        "add": AsyncMock(),
        "delete": AsyncMock(),
        "claim_state": AsyncMock(return_value=True),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _service(
    repository,
    *,
    storage=None,
    projects=None,
    index=None,
    idempotency=None,
) -> ProjectFileService:
    project_service = projects or AsyncMock()
    project_service.require_owned.return_value = project()
    return ProjectFileService(
        repository,
        project_service,
        storage or Mock(),
        StorageLocationFactory(storage_config()),
        index or AsyncMock(),
        idempotency or AsyncMock(),
        file_config(),
        storage_config(),
    )


class ProjectFileServiceTest(IsolatedAsyncioTestCase):
    async def test_upload_persists_and_stores_active_file(self) -> None:
        """验证文件上传成功后形成 active 数据库记录。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param idempotency_key: 本次上传的幂等键。
        @Param relative_path: 合法且未被占用的相对路径。
        @Param source_mtime_ms: 非负源文件修改时间。
        @Param content: 非空且未超限的文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: success 为 True 且状态为 active 的 ProjectFileUploadResponse。
        @SideEffect: 声明幂等键、创建数据库记录并写入 MinIO。
        """
        repository = _repository()

        async def assign_id(file: ProjectFile) -> ProjectFile:
            file.id = 30
            return file

        repository.add.side_effect = assign_id
        storage = Mock()
        idempotency = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            idempotency=idempotency,
        )
        content = b"sensitive file content"

        with patch.object(project_file_service_module, "logger") as logger:
            result = await service.upload(
                user_id=1,
                project_id=10,
                idempotency_key="upload-key",
                relative_path="private/README.md",
                source_mtime_ms=100,
                content=content,
                supplied_content_type="text/markdown",
            )

        file = repository.add.await_args.args[0]
        self.assertTrue(result.success)
        self.assertEqual("active", result.status)
        self.assertEqual("success", result.upload_status)
        self.assertEqual("active", file.status)
        idempotency.claim.assert_awaited_once_with(
            1,
            "file:upload:10:private/README.md",
            "upload-key",
        )
        storage.put_bytes.assert_called_once()
        self.assertEqual(2, repository.session.commit.await_count)
        calls = repr(logger.method_calls)
        self.assertIn("action=project_file.upload", calls)
        self.assertNotIn("sensitive file content", calls)
        self.assertNotIn("private/README.md", calls)
        self.assertNotIn(file.object_key, calls)

    async def test_upload_rejects_existing_path(self) -> None:
        """验证文件路径已存在时拒绝重复上传。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param idempotency_key: 本次上传的幂等键。
        @Param relative_path: 已被项目文件占用的相对路径。
        @Param source_mtime_ms: 非负源文件修改时间。
        @Param content: 合法文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 抛出 FILE_PATH_CONFLICT 的 AppException。
        """
        repository = _repository(
            find_path=AsyncMock(return_value=project_file())
        )
        storage = Mock()
        service = _service(repository, storage=storage)

        with self.assertRaises(AppException) as caught:
            await service.upload(
                1,
                10,
                "upload-key",
                "docs/README.md",
                100,
                b"content",
                "text/markdown",
            )

        self.assertIs(ErrorCode.FILE_PATH_CONFLICT, caught.exception.error)
        repository.add.assert_not_awaited()
        storage.put_bytes.assert_not_called()

    async def test_upload_rolls_back_database_conflict(self) -> None:
        """验证文件记录唯一约束冲突会回滚事务。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param idempotency_key: 本次上传的幂等键。
        @Param relative_path: 预查询未发现冲突的相对路径。
        @Param source_mtime_ms: 非负源文件修改时间。
        @Param content: 合法文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 抛出 FILE_PATH_CONFLICT 的 AppException。
        @SideEffect: 回滚数据库事务且不写入 MinIO。
        """
        repository = _repository(
            add=AsyncMock(
                side_effect=IntegrityError("insert", {}, RuntimeError("duplicate"))
            )
        )
        storage = Mock()
        service = _service(repository, storage=storage)

        with self.assertRaises(AppException) as caught:
            await service.upload(
                1,
                10,
                "upload-key",
                "docs/README.md",
                100,
                b"content",
                "text/markdown",
            )

        self.assertIs(ErrorCode.FILE_PATH_CONFLICT, caught.exception.error)
        repository.session.rollback.assert_awaited_once()
        storage.put_bytes.assert_not_called()

    async def test_upload_keeps_diagnostic_state_on_storage_failure(self) -> None:
        """验证 MinIO 写入失败时保留可诊断状态。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param idempotency_key: 本次上传的幂等键。
        @Param relative_path: 合法且未被占用的相对路径。
        @Param source_mtime_ms: 非负源文件修改时间。
        @Param content: 合法文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: success 为 False 且包含 FILE_STORAGE_ERROR 的上传响应。
        @SideEffect: 将数据库记录更新为 upload_failed/failed。
        """
        repository = _repository()

        async def assign_id(file: ProjectFile) -> ProjectFile:
            file.id = 30
            return file

        repository.add.side_effect = assign_id
        storage = Mock()
        storage.put_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        service = _service(repository, storage=storage)

        result = await service.upload(
            1,
            10,
            "upload-key",
            "docs/README.md",
            100,
            b"content",
            "text/markdown",
        )

        file = repository.add.await_args.args[0]
        self.assertFalse(result.success)
        self.assertEqual("upload_failed", result.status)
        self.assertEqual("failed", result.upload_status)
        self.assertEqual("FILE_STORAGE_ERROR", result.error_code)
        self.assertEqual("FILE_STORAGE_ERROR", file.last_error_code)
        self.assertIsNotNone(file.last_failed_at)
        self.assertEqual(2, repository.session.commit.await_count)

    async def test_overwrite_skips_storage_when_content_is_unchanged(self) -> None:
        """验证相同内容覆盖只更新元数据和索引。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param idempotency_key: 本次覆盖的幂等键。
        @Param source_mtime_ms: 新的源文件修改时间。
        @Param lock_version: 与文件一致的乐观锁版本。
        @Param content: 与现有内容哈希相同的文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 仍为 active 的 ProjectFileResponse。
        @SideEffect: 声明更新状态、提交元数据并重建索引，不写入 MinIO。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)

        result = await service.overwrite(
            1,
            10,
            30,
            "overwrite-key",
            200,
            0,
            b"original content",
            "text/markdown",
        )

        self.assertEqual("active", result.status)
        self.assertEqual(200, result.source_mtime_ms)
        storage.put_bytes.assert_not_called()
        index.write.assert_awaited_once()

    async def test_overwrite_retries_then_succeeds(self) -> None:
        """验证文件覆盖在临时存储失败后能够重试成功。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param idempotency_key: 本次覆盖的幂等键。
        @Param source_mtime_ms: 新的源文件修改时间。
        @Param lock_version: 与文件一致的乐观锁版本。
        @Param content: 与现有内容不同的新文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 内容和上传状态已更新的 ProjectFileResponse。
        @SideEffect: 第一次 MinIO 写入失败后重试，最终提交状态并重建索引。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        storage.put_bytes.side_effect = [
            AppException(ErrorCode.FILE_STORAGE_ERROR),
            None,
        ]
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)

        result = await service.overwrite(
            1,
            10,
            30,
            "overwrite-key",
            200,
            0,
            b"updated content",
            "text/plain",
        )

        self.assertEqual("active", result.status)
        self.assertEqual("success", result.upload_status)
        self.assertEqual(2, storage.put_bytes.call_count)
        self.assertIsNone(file.last_error_code)
        index.write.assert_awaited_once()

    async def test_overwrite_raises_after_retry_exhaustion(self) -> None:
        """验证文件覆盖连续失败后进入终态并停止重试。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param idempotency_key: 本次覆盖的幂等键。
        @Param source_mtime_ms: 新的源文件修改时间。
        @Param lock_version: 与文件一致的乐观锁版本。
        @Param content: 与现有内容不同的新文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 抛出 FILE_UPLOAD_RETRY_EXHAUSTED 的 AppException。
        @SideEffect: 连续三次写入失败后保存 upload_failed 状态并重建索引。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        storage.put_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)

        with self.assertRaises(AppException) as caught:
            await service.overwrite(
                1,
                10,
                30,
                "overwrite-key",
                200,
                0,
                b"updated content",
                "text/plain",
            )

        self.assertIs(ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED, caught.exception.error)
        self.assertEqual("upload_failed", file.status)
        self.assertEqual("failed", file.upload_status)
        self.assertEqual(3, storage.put_bytes.call_count)
        index.write.assert_awaited_once()

    async def test_overwrite_rejects_invalid_state_version_or_claim(self) -> None:
        """验证文件覆盖拒绝非法状态、过期版本和并发状态冲突。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: 待覆盖文件 ID。
        @Param idempotency_key: 本次覆盖的幂等键。
        @Param source_mtime_ms: 新的源文件修改时间。
        @Param lock_version: 参数化的乐观锁版本。
        @Param content: 合法的新文件内容。
        @Param supplied_content_type: 合法 MIME 类型。
        @Return: 抛出 FILE_STATUS_INVALID 或 FILE_BUSY 的 AppException。
        """
        cases = [
            (project_file(status="updating"), True, ErrorCode.FILE_STATUS_INVALID),
            (project_file(lock_version=2), True, ErrorCode.FILE_BUSY),
            (project_file(), False, ErrorCode.FILE_BUSY),
        ]

        for file, claimed, expected_error in cases:
            with self.subTest(error=expected_error, claimed=claimed):
                repository = _repository(
                    file,
                    claim_state=AsyncMock(return_value=claimed),
                )
                service = _service(repository)
                with self.assertRaises(AppException) as caught:
                    await service.overwrite(
                        1,
                        10,
                        30,
                        "overwrite-key",
                        200,
                        0,
                        b"updated content",
                        "text/plain",
                    )
                self.assertIs(expected_error, caught.exception.error)

    async def test_update_path_changes_metadata_without_storage_move(self) -> None:
        """验证文件名不变时仅更新路径元数据。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param request: 文件名不变且路径变化的修改请求。
        @Return: 包含新相对路径的 ProjectFileResponse。
        @SideEffect: 提交路径元数据并重建索引，不复制 MinIO 对象。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)
        request = UpdateProjectFilePathRequest(
            relative_path="renamed/README.md",
            source_mtime_ms=200,
            lock_version=0,
        )

        result = await service.update_path(1, 10, 30, request)

        self.assertEqual("renamed/README.md", result.relative_path)
        storage.copy.assert_not_called()
        storage.remove.assert_not_called()
        index.write.assert_awaited_once()

    async def test_update_path_moves_object_when_file_name_changes(self) -> None:
        """验证文件名变化时复制新对象并删除旧对象。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param request: 包含新文件名的路径修改请求。
        @Return: 存储名称和对象位置已更新的 ProjectFileResponse。
        @SideEffect: 复制 MinIO 对象、提交新位置、删除旧对象并重建索引。
        """
        file = project_file()
        old_object_key = file.object_key
        repository = _repository(file)
        storage = Mock()
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)
        request = UpdateProjectFilePathRequest(
            relative_path="docs/GUIDE.md",
            source_mtime_ms=200,
            lock_version=0,
        )

        result = await service.update_path(1, 10, 30, request)

        self.assertEqual("GUIDE.md", result.file_name)
        self.assertNotEqual(old_object_key, file.object_key)
        storage.copy.assert_called_once()
        storage.remove.assert_called_once()
        index.write.assert_awaited_once()

    async def test_update_path_rejects_target_conflict(self) -> None:
        """验证目标路径被其他文件占用时拒绝修改。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param request: 路径哈希与其他文件冲突的修改请求。
        @Return: 抛出 FILE_PATH_CONFLICT 的 AppException。
        """
        file = project_file()
        repository = _repository(
            file,
            find_path=AsyncMock(return_value=project_file(file_id=31)),
        )
        storage = Mock()
        service = _service(repository, storage=storage)
        request = UpdateProjectFilePathRequest(
            relative_path="docs/GUIDE.md",
            source_mtime_ms=200,
            lock_version=0,
        )

        with self.assertRaises(AppException) as caught:
            await service.update_path(1, 10, 30, request)

        self.assertIs(ErrorCode.FILE_PATH_CONFLICT, caught.exception.error)
        repository.claim_state.assert_not_awaited()
        storage.copy.assert_not_called()

    async def test_update_path_restores_active_state_when_copy_fails(self) -> None:
        """验证新对象复制失败时恢复原文件 active 状态。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param request: 包含新文件名的路径修改请求。
        @Return: 抛出 FILE_RENAME_FAILED 的 AppException。
        @SideEffect: 保存 active 恢复状态且不删除旧对象。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        storage.copy.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        service = _service(repository, storage=storage)
        request = UpdateProjectFilePathRequest(
            relative_path="docs/GUIDE.md",
            source_mtime_ms=200,
            lock_version=0,
        )

        with self.assertRaises(AppException) as caught:
            await service.update_path(1, 10, 30, request)

        self.assertIs(ErrorCode.FILE_RENAME_FAILED, caught.exception.error)
        self.assertEqual("active", file.status)
        storage.remove.assert_not_called()

    async def test_update_path_marks_verify_required_when_old_remove_fails(self) -> None:
        """验证旧对象删除失败时保留待核验状态。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param request: 包含新文件名的路径修改请求。
        @Return: 抛出 FILE_RENAME_FAILED 的 AppException。
        @SideEffect: 新对象已保存，文件转为 verify_required 并重建索引。
        """
        file = project_file()
        repository = _repository(file)
        storage = Mock()
        storage.remove.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)
        request = UpdateProjectFilePathRequest(
            relative_path="docs/GUIDE.md",
            source_mtime_ms=200,
            lock_version=0,
        )

        with self.assertRaises(AppException) as caught:
            await service.update_path(1, 10, 30, request)

        self.assertIs(ErrorCode.FILE_RENAME_FAILED, caught.exception.error)
        self.assertEqual("verify_required", file.status)
        index.write.assert_awaited_once()

    async def test_list_files_returns_public_business_files(self) -> None:
        """验证文件列表返回指定公开业务类型的数据。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param business_code: project 公开业务类型。
        @Return: 仓储文件映射形成的 ProjectFileResponse 列表。
        """
        files = [project_file(file_id=30), project_file(file_id=31)]
        repository = _repository(list=AsyncMock(return_value=files))
        service = _service(repository)

        result = await service.list_files(1, 10, "project")

        self.assertEqual([30, 31], [file.id for file in result])
        repository.list.assert_awaited_once_with(10, "project")

    async def test_list_files_rejects_system_or_invalid_business(self) -> None:
        """验证文件列表拒绝系统文件和未知业务类型。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param business_code: system 或未知业务类型。
        @Return: 抛出 SYSTEM_FILE_ACCESS_DENIED 或 PARAM_INVALID 的 AppException。
        """
        cases = [
            ("system", ErrorCode.SYSTEM_FILE_ACCESS_DENIED),
            ("unknown", ErrorCode.PARAM_INVALID),
        ]

        for business_code, expected_error in cases:
            with self.subTest(business_code=business_code):
                repository = _repository()
                service = _service(repository)
                with self.assertRaises(AppException) as caught:
                    await service.list_files(1, 10, business_code)
                self.assertIs(expected_error, caught.exception.error)
                repository.list.assert_not_awaited()

    async def test_create_read_url_returns_expiring_url(self) -> None:
        """验证 active 文件能够签发限时读取地址。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 公开文件 ID。
        @Return: 包含预签名 URL 和过期时间的 FileReadUrlResponse。
        @SideEffect: 调用 MinIO 预签名地址生成方法。
        """
        repository = _repository(project_file())
        storage = Mock()
        storage.presigned_get.return_value = "https://storage.example/read"
        service = _service(repository, storage=storage)

        result = await service.create_read_url(1, 10, 30)

        self.assertEqual(30, result.file_id)
        self.assertEqual("https://storage.example/read", result.url)
        self.assertGreater(result.expires_at, datetime.now())
        storage.presigned_get.assert_called_once()

    async def test_create_read_url_rejects_inaccessible_file(self) -> None:
        """验证读取地址不会暴露不存在、系统或非 active 文件。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: 不可公开读取的文件 ID。
        @Return: 抛出 FILE_NOT_FOUND、SYSTEM_FILE_ACCESS_DENIED 或 FILE_STATUS_INVALID。
        """
        cases = [
            (None, ErrorCode.FILE_NOT_FOUND),
            (
                project_file(business_code="system"),
                ErrorCode.SYSTEM_FILE_ACCESS_DENIED,
            ),
            (project_file(status="upload_failed"), ErrorCode.FILE_STATUS_INVALID),
        ]

        for file, expected_error in cases:
            with self.subTest(error=expected_error):
                storage = Mock()
                service = _service(_repository(file), storage=storage)
                with self.assertRaises(AppException) as caught:
                    await service.create_read_url(1, 10, 30)
                self.assertIs(expected_error, caught.exception.error)
                storage.presigned_get.assert_not_called()

    async def test_delete_removes_object_record_and_rebuilds_index(self) -> None:
        """验证文件删除成功后清理记录并重建索引。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param lock_version: 与文件一致的乐观锁版本。
        @Return: None，操作成功完成。
        @SideEffect: 删除 MinIO 对象和数据库记录，并重建项目索引。
        """
        repository = _repository(project_file())
        storage = Mock()
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)

        await service.delete(1, 10, 30, 0)

        storage.remove.assert_called_once()
        repository.delete.assert_awaited_once_with(30)
        index.write.assert_awaited_once()

    async def test_delete_marks_failure_state_when_cleanup_fails(self) -> None:
        """验证文件删除失败后保存 delete_failed 状态。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 目标项目 ID。
        @Param file_id: active 文件 ID。
        @Param lock_version: 与文件一致的乐观锁版本。
        @Return: 继续抛出底层 RuntimeError。
        @SideEffect: 回滚删除事务并提交 delete_failed 恢复状态。
        """
        file = project_file()
        current = project_file()
        repository = _repository(
            file,
            get=AsyncMock(side_effect=[file, current]),
        )
        storage = Mock()
        storage.remove.side_effect = RuntimeError("storage failed")
        index = AsyncMock()
        service = _service(repository, storage=storage, index=index)

        with self.assertRaises(RuntimeError):
            await service.delete(1, 10, 30, 0)

        repository.session.rollback.assert_awaited_once()
        self.assertEqual("delete_failed", current.status)
        index.write.assert_not_awaited()
