"""项目文件分析与上下文发布编排服务单元测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.chat.runs.service import RunService
from app.modules.project_file.analysis import service as analysis_service_module
from app.modules.project_file.analysis.schemas import ProjectFileAnalysisBatchResult
from app.modules.project_file.analysis.service import ProjectFileAnalysisService
from app.project_context.file_detail.schemas import FileSemanticAnalysisResult

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
        "list_analysis_candidates": AsyncMock(return_value=candidates),
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
    content_extractor=None,
    semantic_analyzer=None,
    specification=None,
    runs=None,
) -> ProjectFileAnalysisService:
    project_service = projects or AsyncMock()
    project_service.require_owned.return_value = project()
    specification_service = specification or AsyncMock()
    if not isinstance(specification_service.refresh.return_value, str):
        specification_service.refresh.return_value = "updated"
    run_service = runs if runs is not None else AsyncMock(spec=RunService)
    run_service.start.return_value = (SimpleNamespace(id=90000000000000001), True)
    return ProjectFileAnalysisService(
        repository,
        project_service,
        storage or Mock(),
        StorageLocationFactory(storage_config()),
        index or AsyncMock(),
        content_extractor or AsyncMock(),
        semantic_analyzer or AsyncMock(),
        specification_service,
        runs=run_service,
    )


def _success_result(file, *, may_supply_project_constraints: bool = False):
    detail_ref = (
        f"system/file_details/{file.storage_uuid}-{file.content_hash}-"
        f"{file.path_hash}.json"
    )
    detail = file_detail(file).model_copy(
        update={
            "detail_ref": detail_ref,
            "may_supply_project_constraints": may_supply_project_constraints,
        }
    )
    return FileSemanticAnalysisResult(
        project_id=file.project_id,
        file_id=file.id,
        content_hash=file.content_hash,
        status="success",
        detail=detail,
    )


def _failure_result(file):
    return FileSemanticAnalysisResult(
        project_id=file.project_id,
        file_id=file.id,
        content_hash=file.content_hash,
        status="failed",
        error_code="MODEL_OUTPUT_INVALID",
        error_message="模型输出不合法",
    )


class ProjectFileAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_document_project_fact_becomes_verified_long_term_memory(
        self,
    ) -> None:
        """核心文档中可定位的事实会形成带来源的长期记忆条目。"""
        file = project_file(file_id=30, relative_path="docs/roadmap.md")
        file.detail_ref = "system/file_details/roadmap.json"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "project_facts": [
                    {
                        "kind": "planned_capability",
                        "statement": "下一阶段完成风险看板",
                        "source_quote": "下一阶段完成风险看板",
                        "source_range": {"start_line": 8, "end_line": 8},
                        "evidence_verified": True,
                    }
                ],
            }
        )
        entries = ProjectFileAnalysisService._memory_entries(10, detail, {})

        self.assertEqual(1, len(entries))
        self.assertEqual("long_memory", entries[0]["kind"])
        self.assertEqual("planned", entries[0]["attributes"]["state"])
        self.assertEqual(8, entries[0]["attributes"]["sourceRange"]["start_line"])
        self.assertEqual(file.content_hash, entries[0]["attributes"]["contentHash"])

    async def test_unverified_document_project_fact_is_not_published(self) -> None:
        """无法在当前原文唯一定位的模型事实不会进入长期记忆。"""
        file = project_file(file_id=30, relative_path="docs/roadmap.md")
        file.may_supply_constraints = True
        file.detail_ref = "system/file_details/roadmap.json"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "project_facts": [
                    {
                        "kind": "completed_capability",
                        "statement": "风险看板已经完成",
                        "source_quote": "",
                        "evidence_verified": False,
                    }
                ],
            }
        )
        self.assertEqual([], ProjectFileAnalysisService._memory_entries(10, detail, {}))

    async def test_code_fact_becomes_observed_memory_but_never_project_constraint(
        self,
    ) -> None:
        """代码可提供当前实现观察，但不因其风格反推项目约束。"""
        file = project_file(file_id=31, relative_path="app/risk/service.py")
        file.may_supply_constraints = False
        file.detail_ref = "system/file_details/risk-service.json"
        detail = file_detail(file).model_copy(
            update={
                "detail_ref": file.detail_ref,
                "kind": "source_code",
                "file_type": "code",
                "project_facts": [
                    {
                        "kind": "completed_capability",
                        "statement": "已经实现风险评分函数",
                        "source_quote": "def risk_score(probability, impact):",
                        "source_range": {"start_line": 22, "end_line": 22},
                        "evidence_verified": True,
                    }
                ],
            }
        )
        entries = ProjectFileAnalysisService._memory_entries(10, detail, {})

        self.assertEqual(1, len(entries))
        self.assertEqual("long_memory", entries[0]["kind"])
        self.assertEqual("observed_complete", entries[0]["attributes"]["state"])
        self.assertFalse(file.may_supply_constraints)

    async def test_analyze_pending_files_persists_mixed_results(self) -> None:
        """验证项目文件分析会分别保存成功和失败结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待分析项目 ID。
        @Return: None，所有候选文件处理完成。
        @SideEffect: 读取文件、写入成功详情、记录失败原因并重建索引。
        """
        first = project_file(file_id=30)
        second = project_file(file_id=31)
        repository = _repository([first, second])
        storage = Mock()
        storage.read_bytes.return_value = b"sensitive file content"
        content_extractor = AsyncMock()
        content_extractor.extract_from_bytes.return_value = {
            "type": "text",
            "text": "sensitive file content",
        }
        semantic_analyzer = AsyncMock()
        semantic_analyzer.analyze.side_effect = [
            _success_result(first),
            _failure_result(second),
        ]
        index = AsyncMock()
        specification = AsyncMock()
        runs = AsyncMock(spec=RunService)
        service = _service(
            repository,
            storage=storage,
            content_extractor=content_extractor,
            semantic_analyzer=semantic_analyzer,
            index=index,
            specification=specification,
            runs=runs,
        )

        with patch.object(analysis_service_module, "logger") as logger:
            result = await service.analyze_pending_files(1, 10, "parse-request")

        self.assertEqual("partial", result.status)
        self.assertEqual("90000000000000001", result.run_id)
        runs.start.assert_awaited_once()
        runs.finish.assert_awaited_once()
        self.assertEqual("partial", runs.finish.await_args.args[3]["status"])
        self.assertIsNotNone(runs.finish.await_args.kwargs["error"])
        self.assertEqual(2, result.candidate_count)
        self.assertEqual(1, result.success_count)
        self.assertEqual(1, result.failure_count)
        self.assertEqual(31, result.failures[0].file_id)
        self.assertEqual("updated", result.specification_status)
        self.assertEqual("updated", result.index_status)
        self.assertEqual(2, storage.read_bytes.call_count)
        self.assertEqual(2, content_extractor.extract_from_bytes.await_count)
        storage.put_bytes.assert_called_once()
        repository.record_analysis_success.assert_awaited_once_with(
            10,
            30,
            first.content_hash,
            first.lock_version,
            _success_result(first).detail,
            promote_constraint_source=False,
        )
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            31,
            second.content_hash,
            second.lock_version,
            "MODEL_OUTPUT_INVALID",
            "模型输出不合法",
        )
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()
        first_request = semantic_analyzer.analyze.await_args_list[0].args[0]
        self.assertEqual(1, first_request.user_id)
        self.assertEqual(30, first_request.file_id)
        self.assertEqual(first.relative_path, first_request.original_path)
        self.assertEqual(
            (
                f"system/file_details/{first.storage_uuid}-{first.content_hash}-"
                f"{first.path_hash}.json"
            ),
            first_request.detail_ref,
        )
        calls = repr(logger.method_calls)
        self.assertIn("successCount=%s", calls)
        self.assertIn("failureCount=%s", calls)
        self.assertNotIn("sensitive file content", calls)
        self.assertNotIn(first.object_key, calls)

    async def test_model_judgment_only_promotes_constraint_source(self) -> None:
        cases = (
            (False, True, True),
            (True, True, False),
            (False, False, False),
            (True, False, False),
        )
        for offset, (stored, judged, expected) in enumerate(cases):
            with self.subTest(stored=stored, judged=judged):
                file = project_file(file_id=40 + offset)
                file.may_supply_constraints = stored
                repository = _repository([file])
                storage = Mock()
                storage.read_bytes.return_value = b"content"
                content_extractor = AsyncMock()
                content_extractor.extract_from_bytes.return_value = {
                    "type": "text",
                    "text": "content",
                }
                semantic_analyzer = AsyncMock()
                semantic_analyzer.analyze.return_value = _success_result(
                    file,
                    may_supply_project_constraints=judged,
                )
                service = _service(
                    repository,
                    storage=storage,
                    content_extractor=content_extractor,
                    semantic_analyzer=semantic_analyzer,
                )

                await service.analyze_pending_files(
                    1,
                    10,
                    f"constraint-source-{offset}",
                )

                self.assertEqual(
                    expected,
                    repository.record_analysis_success.await_args.kwargs[
                        "promote_constraint_source"
                    ],
                )

    async def test_analyze_pending_files_records_content_extraction_failure(
        self,
    ) -> None:
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.read_bytes.return_value = b"unsupported content"
        content_extractor = AsyncMock()
        content_extractor.extract_from_bytes.side_effect = ValueError(
            "不支持该文件格式"
        )
        semantic_analyzer = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            content_extractor=content_extractor,
            semantic_analyzer=semantic_analyzer,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        semantic_analyzer.analyze.assert_not_awaited()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            file.id,
            file.content_hash,
            file.lock_version,
            "FILE_DETAIL_ANALYSIS_FAILED",
            "文件内容提取失败",
        )
        self.assertEqual("partial", result.status)

    async def test_analyze_pending_files_records_storage_read_failure(self) -> None:
        """验证源文件读取失败会记录文件级失败结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待分析项目 ID。
        @Return: None，失败结果记录完成。
        @SideEffect: 保存 FILE_STORAGE_ERROR 并继续重建项目索引。
        """
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.read_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        content_extractor = AsyncMock()
        semantic_analyzer = AsyncMock()
        index = AsyncMock()
        specification = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            content_extractor=content_extractor,
            semantic_analyzer=semantic_analyzer,
            index=index,
            specification=specification,
        )

        await service.analyze_pending_files(1, 10, "parse-request")

        content_extractor.extract_from_bytes.assert_not_awaited()
        semantic_analyzer.analyze.assert_not_awaited()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            30,
            file.content_hash,
            file.lock_version,
            "FILE_STORAGE_ERROR",
            ErrorCode.FILE_STORAGE_ERROR.message,
        )
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()

    async def test_analyze_pending_files_records_semantic_analyzer_exception(
        self,
    ) -> None:
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.read_bytes.return_value = b"content"
        semantic_analyzer = AsyncMock()
        semantic_analyzer.analyze.side_effect = RuntimeError("model failed")
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            semantic_analyzer=semantic_analyzer,
            index=index,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        repository.record_analysis_success.assert_not_awaited()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            file.id,
            file.content_hash,
            file.lock_version,
            "FILE_DETAIL_ANALYSIS_FAILED",
            "文件语义分析器执行失败",
        )
        index.write.assert_awaited_once()
        self.assertEqual("partial", result.status)
        self.assertEqual("FILE_DETAIL_ANALYSIS_FAILED", result.failures[0].error_code)

    async def test_analyze_pending_files_rolls_back_concurrent_conflict(self) -> None:
        """验证文件内容并发变化时拒绝落库旧分析结果。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 待分析项目 ID。
        @Return: 抛出 SYSTEM_ERROR 的 AppException。
        @SideEffect: 回滚分析结果事务且不重建旧索引。
        """
        file = project_file()
        repository = _repository(
            [file],
            record_analysis_success=AsyncMock(return_value=False),
        )
        storage = Mock()
        storage.read_bytes.return_value = b"content"
        semantic_analyzer = AsyncMock()
        semantic_analyzer.analyze.return_value = _success_result(file)
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            semantic_analyzer=semantic_analyzer,
            index=index,
        )

        with self.assertRaises(AppException) as caught:
            await service.analyze_pending_files(1, 10, "parse-request")

        self.assertIs(ErrorCode.SYSTEM_ERROR, caught.exception.error)
        repository.session.rollback.assert_awaited()
        index.write.assert_not_awaited()
        detail_location = storage.put_bytes.call_args.args[0]
        self.assertIn(file.content_hash, detail_location.object_key)

    async def test_analyze_pending_files_records_detail_storage_failure(
        self,
    ) -> None:
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.read_bytes.return_value = b"content"
        storage.put_bytes.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        semantic_analyzer = AsyncMock(return_value=_success_result(file))
        semantic_analyzer.analyze.return_value = _success_result(file)
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            semantic_analyzer=semantic_analyzer,
            index=index,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        repository.record_analysis_success.assert_not_awaited()
        repository.record_analysis_failure.assert_awaited_once_with(
            10,
            file.id,
            file.content_hash,
            file.lock_version,
            "FILE_STORAGE_ERROR",
            ErrorCode.FILE_STORAGE_ERROR.message,
        )
        self.assertEqual("partial", result.status)
        self.assertEqual("FILE_STORAGE_ERROR", result.failures[0].error_code)
        index.write.assert_awaited_once()

    async def test_analyze_pending_files_rebuilds_index_without_candidates(
        self,
    ) -> None:
        """验证无候选文件时仍从数据库重建完整索引。

        @Param user_id: 项目所有者用户 ID。
        @Param project_id: 当前没有待分析文件的项目 ID。
        @Return: None，索引重建完成。
        @SideEffect: 查询完整文件列表并写入项目索引。
        """
        repository = _repository([])
        index = AsyncMock()
        content_extractor = AsyncMock()
        semantic_analyzer = AsyncMock()
        specification = AsyncMock()
        service = _service(
            repository,
            index=index,
            content_extractor=content_extractor,
            semantic_analyzer=semantic_analyzer,
            specification=specification,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        content_extractor.extract_from_bytes.assert_not_awaited()
        semantic_analyzer.analyze.assert_not_awaited()
        repository.list_analysis_candidates.assert_awaited_once_with(
            10,
            force=False,
        )
        repository.list.assert_awaited_once_with(10, include_system=True)
        index.write.assert_awaited_once()
        specification.refresh.assert_awaited_once()
        self.assertEqual("success", result.status)
        self.assertEqual(0, result.candidate_count)

    async def test_analyze_pending_files_keeps_old_specification(self) -> None:
        file = project_file()
        repository = _repository([file])
        storage = Mock()
        storage.read_bytes.return_value = b"content"
        semantic_analyzer = AsyncMock()
        semantic_analyzer.analyze.return_value = _success_result(file)
        specification = AsyncMock()
        specification.refresh.side_effect = AppException(
            ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
        )
        index = AsyncMock()
        service = _service(
            repository,
            storage=storage,
            semantic_analyzer=semantic_analyzer,
            specification=specification,
            index=index,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        self.assertEqual("partial", result.status)
        self.assertEqual("failed", result.specification_status)
        self.assertEqual("updated", result.index_status)
        index.write.assert_awaited_once()

    async def test_analyze_pending_files_publishes_specification_before_index(
        self,
    ) -> None:
        repository = _repository([])
        calls: list[str] = []
        specification = AsyncMock()

        async def refresh(*_args):
            calls.append("specification")
            return "kept"

        specification.refresh.side_effect = refresh
        index = AsyncMock()

        async def write(*_args):
            calls.append("index")

        index.write.side_effect = write
        service = _service(
            repository,
            specification=specification,
            index=index,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        self.assertEqual(["specification", "index"], calls)
        self.assertEqual("kept", result.specification_status)

    async def test_analyze_pending_files_forwards_force_selection(self) -> None:
        repository = _repository([])
        service = _service(repository)

        await service.analyze_pending_files(1, 10, "parse-request", force=True)

        repository.list_analysis_candidates.assert_awaited_once_with(
            10,
            force=True,
        )

    async def test_analysis_uses_client_key_and_normalizes_selection(self) -> None:
        selected = project_file()
        repository = _repository([], get=AsyncMock(return_value=selected))
        runs = AsyncMock(spec=RunService)
        service = _service(repository, runs=runs)

        await service.analyze_pending_files(
            1,
            10,
            " parse-request ",
            force=True,
            file_ids=[31, 30, 31],
        )

        self.assertEqual(" parse-request ", runs.start.await_args.args[3])
        self.assertEqual(
            {"force": True, "fileIds": [30, 31]}, runs.start.await_args.args[4]
        )
        self.assertEqual(
            "project-file-parse:10",
            runs.start.await_args.kwargs["exclusive_scope"],
        )
        repository.list_analysis_candidates.assert_awaited_once_with(
            10,
            force=True,
            file_ids=[30, 31],
        )

    async def test_duplicate_completed_batch_reuses_archived_result(self) -> None:
        repository = _repository([])
        runs = AsyncMock(spec=RunService)
        service = _service(repository, runs=runs)
        archived = ProjectFileAnalysisBatchResult(
            run_id="90000000000000001",
            status="success",
            candidate_count=1,
            success_count=1,
            failure_count=0,
            failures=[],
            specification_status="updated",
            index_status="updated",
        )
        runs.start.return_value = (
            SimpleNamespace(
                id=90000000000000001,
                status="success",
                result=archived.model_dump(mode="json", by_alias=True),
            ),
            False,
        )

        result = await service.analyze_pending_files(1, 10, "parse-request")

        self.assertEqual(archived, result)
        repository.list_analysis_candidates.assert_not_awaited()
        runs.finish.assert_not_awaited()

    async def test_duplicate_running_batch_does_not_execute_again(self) -> None:
        repository = _repository([])
        runs = AsyncMock(spec=RunService)
        service = _service(repository, runs=runs)
        runs.start.return_value = (
            SimpleNamespace(
                id=90000000000000001,
                status="running",
                result={},
            ),
            False,
        )

        with self.assertRaisesRegex(AppException, "仍在执行"):
            await service.analyze_pending_files(1, 10, "parse-request")

        repository.list_analysis_candidates.assert_not_awaited()
        runs.finish.assert_not_awaited()

    async def test_successful_batch_records_run_result(self) -> None:
        runs = AsyncMock(spec=RunService)
        service = _service(_repository([]), runs=runs)

        result = await service.analyze_pending_files(1, 10, "parse-request")

        self.assertEqual("90000000000000001", result.run_id)
        runs.finish.assert_awaited_once_with(
            90000000000000001,
            1,
            [],
            result.model_dump(mode="json", by_alias=True),
            error=None,
        )

    async def test_interrupted_batch_records_failure_and_propagates(self) -> None:
        repository = _repository(
            [],
            list_analysis_candidates=AsyncMock(
                side_effect=RuntimeError("模拟解析中断")
            ),
        )
        runs = AsyncMock(spec=RunService)
        service = _service(repository, runs=runs)

        with self.assertRaisesRegex(RuntimeError, "模拟解析中断"):
            await service.analyze_pending_files(1, 10, "parse-request")

        repository.session.rollback.assert_awaited_once()
        runs.finish.assert_awaited_once_with(
            90000000000000001,
            1,
            [],
            error="解析运行失败：RuntimeError",
        )

    async def test_cancelled_batch_records_cancellation(self) -> None:
        repository = _repository(
            [], list_analysis_candidates=AsyncMock(side_effect=asyncio.CancelledError())
        )
        runs = AsyncMock(spec=RunService)
        service = _service(repository, runs=runs)

        with self.assertRaises(asyncio.CancelledError):
            await service.analyze_pending_files(1, 10, "parse-request")

        runs.cancel.assert_awaited_once_with(90000000000000001, 1, [])
        runs.finish.assert_not_awaited()
