"""项目文件解析编排服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project_file.analysis import service as analysis_service_module
from app.modules.project_file.analysis.service import ProjectFileAnalysisService
from app.project.context.detail_analysis.schemas import FileAnalysisResult
from tests.unit.modules.project_file.analysis.factories import file_detail
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)


def _repository(candidates, **overrides):
    defaults = {
        "session": SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
        ),
        "list_parse_candidates": AsyncMock(return_value=candidates),
        "record_analysis_success": AsyncMock(return_value=True),
        "record_analysis_failure": AsyncMock(return_value=True),
        "list": AsyncMock(return_value=candidates),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _service(
    repository,
    *,
    storage=None,
    projects=None,
    index=None,
    analyzer=None,
    specification=None,
) -> ProjectFileAnalysisService:
    project_service = projects or AsyncMock()
    project_service.require_owned.return_value = project()
    return ProjectFileAnalysisService(
        repository,
        project_service,
        storage or Mock(),
        StorageLocationFactory(storage_config()),
        index or AsyncMock(),
        analyzer or AsyncMock(),
        specification or AsyncMock(),
    )


def _success_result(file):
    return FileAnalysisResult(
        project_id=file.project_id,
        file_id=file.id,
        content_hash=file.content_hash,
        analysis_version="file-detail-v1",
        status="success",
        detail=file_detail(file),
    )


def _failure_result(file):
    return FileAnalysisResult(
        project_id=file.project_id,
        file_id=file.id,
        content_hash=file.content_hash,
        analysis_version="file-detail-v1",
        status="failed",
        error_code="MODEL_OUTPUT_INVALID",
        error_message="模型输出不合法",
    )


class ProjectFileAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_initialize_persists_mixed_results_and_rebuilds_index(self) -> None:
        """验证项目文件解析会分别保存成功和失败结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待解析项目 ID。
        @Return: None，所有候选文件处理完成。
        @SideEffect: 读取文件、写入成功详情、记录失败原因并重建索引。
        """
        first = project_file(file_id=30)
        second = project_file(file_id=31)
        repository = _repository([first, second])
        storage = Mock()
        storage.get_bytes.return_value = b"sensitive file content"
        analyzer = AsyncMock()
        analyzer.analyze_bytes.side_effect = [
            _success_result(first),
            _failure_result(second),
        ]
        index = AsyncMock()
        specification = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            analyzer=analyzer,
            index=index,
            specification=specification,
        )

        with patch.object(analysis_service_module, "logger") as logger:
            result = await service.initialize(1, 10)

        self.assertIsNone(result)
        self.assertEqual(2, storage.get_bytes.call_count)
        storage.put_bytes.assert_called_once()
        repository.record_analysis_success.assert_awaited_once()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            31,
            second.content_hash,
            "MODEL_OUTPUT_INVALID",
            "模型输出不合法",
        )
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()
        first_request = analyzer.analyze_bytes.await_args_list[0].args[0]
        self.assertEqual(1, first_request.user_id)
        self.assertEqual(30, first_request.file_id)
        self.assertEqual(first.relative_path, first_request.original_path)
        self.assertTrue(first_request.detail_ref.startswith("system/file_details/"))
        calls = repr(logger.method_calls)
        self.assertIn("successCount=%s", calls)
        self.assertIn("failureCount=%s", calls)
        self.assertNotIn("sensitive file content", calls)
        self.assertNotIn(first.object_key, calls)

    async def test_initialize_records_storage_read_failure(self) -> None:
        """验证源文件读取失败会记录文件级失败结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待解析项目 ID。
        @Return: None，失败结果记录完成。
        @SideEffect: 保存 FILE_STORAGE_ERROR 并继续重建项目索引。
        """
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.get_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        analyzer = AsyncMock()
        index = AsyncMock()
        specification = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            analyzer=analyzer,
            index=index,
            specification=specification,
        )

        await service.initialize(1, 10)

        analyzer.analyze_bytes.assert_not_awaited()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            30,
            file.content_hash,
            "FILE_STORAGE_ERROR",
            ErrorCode.FILE_STORAGE_ERROR.message,
        )
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()

    async def test_initialize_propagates_analyzer_exception(self) -> None:
        """验证分析器系统异常不会被错误转换为文件级成功。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待解析项目 ID。
        @Return: 继续抛出分析器产生的 RuntimeError。
        """
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.get_bytes.return_value = b"content"
        analyzer = AsyncMock()
        analyzer.analyze_bytes.side_effect = RuntimeError("model failed")
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            analyzer=analyzer,
            index=index,
        )

        with self.assertRaises(RuntimeError):
            await service.initialize(1, 10)

        repository.record_analysis_success.assert_not_awaited()
        repository.record_analysis_failure.assert_not_awaited()
        index.write.assert_not_awaited()

    async def test_initialize_rolls_back_concurrent_analysis_conflict(self) -> None:
        """验证文件内容并发变化时拒绝落库旧分析结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待解析项目 ID。
        @Return: 抛出 SYSTEM_ERROR 的 AppException。
        @SideEffect: 回滚分析结果事务且不重建旧索引。
        """
        file = project_file()
        repository = _repository(
            [file],
            record_analysis_success=AsyncMock(return_value=False),
        )
        storage = Mock()
        storage.get_bytes.return_value = b"content"
        analyzer = AsyncMock()
        analyzer.analyze_bytes.return_value = _success_result(file)
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            analyzer=analyzer,
            index=index,
        )

        with self.assertRaises(AppException) as caught:
            await service.initialize(1, 10)

        self.assertIs(ErrorCode.SYSTEM_ERROR, caught.exception.error)
        repository.session.rollback.assert_awaited_once()
        index.write.assert_not_awaited()

    async def test_initialize_rebuilds_index_without_candidates(self) -> None:
        """验证无候选文件时仍从数据库重建完整索引。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 当前没有待解析文件的项目 ID。
        @Return: None，索引重建完成。
        @SideEffect: 查询完整文件列表并写入项目索引。
        """
        repository = _repository([])
        index = AsyncMock()
        analyzer = AsyncMock()
        specification = AsyncMock()
        service = _service(
            repository,
            index=index,
            analyzer=analyzer,
            specification=specification,
        )

        await service.initialize(1, 10)

        analyzer.analyze_bytes.assert_not_awaited()
        repository.list.assert_awaited_once_with(10, include_system=True)
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()
