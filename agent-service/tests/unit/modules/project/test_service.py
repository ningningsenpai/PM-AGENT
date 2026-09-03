"""项目业务服务单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.modules.project import service as project_service_module
from app.modules.project.domain import ProjectRecordStatus
from app.modules.project.models import Project
from app.modules.project.schemas import CreateProjectRequest
from app.modules.project.service import ProjectService


def _project(
    *,
    project_id: int = 12,
    owner_user_id: int = 7,
    project_name: str = "PM-Agent",
    status: str = "active",
    record_status: str = "enabled",
) -> Project:
    project = Project(
        owner_user_id=owner_user_id,
        project_name=project_name,
        status=status,
        record_status=record_status,
    )
    project.id = project_id
    project.created_at = datetime(2026, 7, 27, 9, 0, 0)
    project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
    return project


def _repository(**overrides):
    defaults = {
        "session": SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
            refresh=AsyncMock(),
        ),
        "find_enabled_by_owner_and_name": AsyncMock(return_value=None),
        "list_by_owner": AsyncMock(return_value=[]),
        "get_by_id": AsyncMock(return_value=None),
        "add": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _id_generator(value: int = 12) -> Mock:
    generator = Mock()
    generator.next_id.return_value = value
    return generator


def _service(
    repository,
    id_generator=None,
    index=None,
    specification=None,
    chat_context=None,
) -> ProjectService:
    return ProjectService(
        repository,
        id_generator or _id_generator(),
        index or AsyncMock(),
        specification or AsyncMock(),
        chat_context or AsyncMock(),
    )


class ProjectServiceTest(IsolatedAsyncioTestCase):
    async def test_create_initializes_and_activates_project(self) -> None:
        """验证新项目在索引初始化成功后进入 active 状态。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 包含唯一项目名称的 CreateProjectRequest。
        @Return: 状态为 active 的 ProjectResponse。
        @SideEffect: 创建项目记录、初始化索引并提交状态变更。
        """
        repository = _repository()

        async def stamp_timestamps(project: Project) -> Project:
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = stamp_timestamps
        index = AsyncMock()
        specification = AsyncMock()
        chat_context = AsyncMock()
        order: list[str] = []

        async def initialize_specification(*_args):
            order.append("specification")

        async def initialize_index(*_args):
            order.append("index")

        async def initialize_chat_context(*_args):
            order.append("chat_context")

        specification.initialize.side_effect = initialize_specification
        chat_context.initialize.side_effect = initialize_chat_context
        index.initialize.side_effect = initialize_index
        service = _service(
            repository,
            index=index,
            specification=specification,
            chat_context=chat_context,
        )

        with patch.object(project_service_module, "logger") as logger:
            result = await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        created = repository.add.await_args.args[0]
        self.assertEqual(12, created.id)
        self.assertEqual("active", created.status)
        self.assertEqual("enabled", created.record_status)
        self.assertEqual("active", result.status)
        specification.initialize.assert_awaited_once_with(created)
        chat_context.initialize.assert_awaited_once_with(created)
        index.initialize.assert_awaited_once_with(created)
        self.assertEqual(["specification", "chat_context", "index"], order)
        self.assertEqual(3, repository.session.commit.await_count)
        self.assertIn("action=project.create", repr(logger.method_calls))
        self.assertNotIn("PM-Agent", repr(logger.method_calls))

    async def test_create_rejects_active_duplicate(self) -> None:
        """验证同一用户不能创建同名活跃项目。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 名称与已有活跃项目相同的 CreateProjectRequest。
        @Return: 抛出 PROJECT_NAME_EXISTS 的 AppException。
        """
        repository = _repository(
            find_enabled_by_owner_and_name=AsyncMock(return_value=_project())
        )
        service = _service(repository)

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(ErrorCode.PROJECT_NAME_EXISTS, caught.exception.error)
        repository.add.assert_not_awaited()

    async def test_create_uses_new_record_when_disabled_duplicate_is_ignored(
        self,
    ) -> None:
        """验证同名已删除项目不参与创建判重。"""
        repository = _repository()

        async def stamp_timestamps(project: Project) -> Project:
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = stamp_timestamps
        service = _service(repository, id_generator=_id_generator(24))

        result = await service.create(
            7,
            CreateProjectRequest(project_name="PM-Agent"),
        )

        self.assertEqual(24, result.id)
        self.assertEqual(ProjectRecordStatus.ENABLED.value, result.record_status)
        repository.find_enabled_by_owner_and_name.assert_awaited_once_with(
            7,
            "PM-Agent",
        )
        repository.add.assert_awaited_once()

    async def test_create_retries_failed_initialization(self) -> None:
        """验证初始化失败的同名项目会复用原记录重试。

        @Param owner_user_id: 原项目所有者用户 ID。
        @Param request: 名称与 init_failed 项目相同的 CreateProjectRequest。
        @Return: 复用原项目 ID 且状态为 active 的 ProjectResponse。
        @SideEffect: 重新初始化索引并提交项目状态。
        """
        existing = _project(status="init_failed")
        repository = _repository(
            find_enabled_by_owner_and_name=AsyncMock(return_value=existing)
        )
        index = AsyncMock()
        specification = AsyncMock()
        chat_context = AsyncMock()
        order: list[str] = []

        specification.initialize.side_effect = lambda *_args: order.append(
            "specification"
        )
        chat_context.initialize.side_effect = lambda *_args: order.append(
            "chat_context"
        )
        index.initialize.side_effect = lambda *_args: order.append("index")
        service = _service(
            repository,
            index=index,
            specification=specification,
            chat_context=chat_context,
        )

        result = await service.create(
            7,
            CreateProjectRequest(project_name="PM-Agent"),
        )

        self.assertEqual(12, result.id)
        self.assertEqual("active", result.status)
        specification.initialize.assert_awaited_once_with(existing)
        chat_context.initialize.assert_awaited_once_with(existing)
        index.initialize.assert_awaited_once_with(existing)
        self.assertEqual(["specification", "chat_context", "index"], order)
        repository.add.assert_not_awaited()
        self.assertEqual(2, repository.session.commit.await_count)

    async def test_create_rolls_back_database_conflict(self) -> None:
        """验证项目记录唯一约束冲突会回滚事务。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 预查询未发现冲突的项目创建请求。
        @Return: 抛出 PROJECT_NAME_EXISTS 的 AppException。
        @SideEffect: 回滚数据库事务。
        """
        repository = _repository(
            add=AsyncMock(
                side_effect=IntegrityError("insert", {}, RuntimeError("duplicate"))
            )
        )
        service = _service(repository)

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(ErrorCode.PROJECT_NAME_EXISTS, caught.exception.error)
        repository.session.rollback.assert_awaited_once()

    async def test_create_keeps_retryable_record_when_index_initialization_fails(
        self,
    ) -> None:
        """验证索引初始化失败时保留可重试项目记录。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 合法且名称唯一的项目创建请求。
        @Return: 继续抛出索引初始化阶段的 AppException。
        @SideEffect: 将项目标记为 init_failed 并保留已生成的规范对象。
        """
        repository = _repository()

        async def stamp_timestamps(project: Project) -> Project:
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = stamp_timestamps
        index = AsyncMock()
        expected = AppException(ErrorCode.PROJECT_INDEX_WRITE_FAILED)
        index.initialize.side_effect = expected
        specification = AsyncMock()
        service = _service(
            repository,
            index=index,
            specification=specification,
        )

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(expected, caught.exception)
        specification.initialize.assert_awaited_once()
        created = repository.add.await_args.args[0]
        self.assertEqual("init_failed", created.status)
        self.assertEqual(3, repository.session.commit.await_count)

    async def test_create_keeps_retryable_record_when_chat_context_fails(
        self,
    ) -> None:
        """验证 Chat 上下文初始化失败时项目保持可重试状态。"""
        repository = _repository()

        async def stamp_timestamps(project: Project) -> Project:
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = stamp_timestamps
        index = AsyncMock()
        specification = AsyncMock()
        chat_context = AsyncMock()
        expected = AppException(ErrorCode.FILE_STORAGE_ERROR)
        chat_context.initialize.side_effect = expected
        service = _service(
            repository,
            index=index,
            specification=specification,
            chat_context=chat_context,
        )

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(expected, caught.exception)
        specification.initialize.assert_awaited_once()
        chat_context.initialize.assert_awaited_once()
        index.initialize.assert_not_awaited()
        created = repository.add.await_args.args[0]
        self.assertEqual("init_failed", created.status)

    async def test_list_owned_maps_repository_projects(self) -> None:
        """验证项目列表只映射当前用户的仓储结果。

        @Param owner_user_id: 当前用户 ID。
        @Return: 仓储项目映射形成的 ProjectResponse 列表。
        """
        repository = _repository(
            list_by_owner=AsyncMock(
                return_value=[
                    _project(project_id=12),
                    _project(project_id=13, project_name="Second"),
                ]
            )
        )
        service = _service(repository)

        result = await service.list_owned(7)

        self.assertEqual([12, 13], [project.id for project in result])
        repository.list_by_owner.assert_awaited_once_with(7)

    async def test_get_owned_rejects_missing_foreign_or_disabled_project(self) -> None:
        """验证详情查询隐藏他人项目并拒绝非 active 项目。

        @Param owner_user_id: 当前用户 ID。
        @Param project_id: 不存在、属于他人或不可用的项目 ID。
        @Return: 分别抛出 PROJECT_NOT_FOUND 或 PROJECT_DISABLED 的 AppException。
        """
        cases = [
            (None, ErrorCode.PROJECT_NOT_FOUND),
            (_project(owner_user_id=8), ErrorCode.PROJECT_NOT_FOUND),
            (
                _project(record_status="disabled"),
                ErrorCode.PROJECT_NOT_FOUND,
            ),
            (_project(status="init_failed"), ErrorCode.PROJECT_DISABLED),
        ]

        for project, expected_error in cases:
            with self.subTest(error=expected_error):
                repository = _repository(get_by_id=AsyncMock(return_value=project))
                service = _service(repository)
                with self.assertRaises(AppException) as caught:
                    await service.get_owned(7, 12)
                self.assertIs(expected_error, caught.exception.error)

    async def test_delete_owned_marks_record_disabled(self) -> None:
        """验证删除项目时记录三十天保留期限。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param project_id: 状态为 active 的项目 ID。
        @Return: None，操作成功完成。
        @SideEffect: 禁用项目、记录删除时间和最早清理时间并提交事务。
        """
        project = _project()
        repository = _repository(get_by_id=AsyncMock(return_value=project))
        service = _service(repository)
        deleted_at = datetime(2026, 9, 3, 10, 0, 0, tzinfo=UTC)

        with patch.object(project_service_module, "datetime") as current_datetime:
            current_datetime.now.return_value = deleted_at
            await service.delete_owned(7, 12)

        self.assertEqual(ProjectRecordStatus.DISABLED.value, project.record_status)
        self.assertEqual(deleted_at, project.deleted_at)
        self.assertEqual(
            datetime(2026, 10, 3, 10, 0, 0, tzinfo=UTC),
            project.purge_after,
        )
        repository.session.commit.assert_awaited_once()

    async def test_delete_owned_rolls_back_database_failure(self) -> None:
        """验证项目状态提交失败时回滚数据库事务。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param project_id: 状态为 active 的项目 ID。
        @Return: 抛出 PROJECT_DELETE_FAILED 的 AppException。
        @SideEffect: 数据库事务被回滚。
        """
        project = _project()
        repository = _repository(
            get_by_id=AsyncMock(return_value=project),
        )
        repository.session.commit.side_effect = RuntimeError("database failed")
        service = _service(repository)

        with self.assertRaises(AppException) as caught:
            await service.delete_owned(7, 12)

        self.assertIs(ErrorCode.PROJECT_DELETE_FAILED, caught.exception.error)
        self.assertEqual(ProjectRecordStatus.DISABLED.value, project.record_status)
        self.assertIsNotNone(project.deleted_at)
        self.assertIsNotNone(project.purge_after)
        repository.session.rollback.assert_awaited_once()
