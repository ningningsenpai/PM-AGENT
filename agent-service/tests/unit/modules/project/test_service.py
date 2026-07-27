"""项目业务服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.exc import IntegrityError

from app.core.config import StorageConfig
from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project import service as project_service_module
from app.modules.project.models import Project
from app.modules.project.schemas import CreateProjectRequest
from app.modules.project.service import ProjectService


def _project(
    *,
    project_id: int = 12,
    owner_user_id: int = 7,
    project_name: str = "PM-Agent",
    status: str = "active",
) -> Project:
    project = Project(
        owner_user_id=owner_user_id,
        project_name=project_name,
        status=status,
    )
    project.id = project_id
    project.created_at = datetime(2026, 7, 27, 9, 0, 0)
    project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
    return project


def _storage_config() -> StorageConfig:
    return StorageConfig(
        endpoint="127.0.0.1:9000",
        access_key="test",
        secret_key="test",
        secure=False,
        bucket="pm-agent-test",
        read_url_expiry_seconds=300,
    )


def _repository(**overrides):
    defaults = {
        "session": SimpleNamespace(
            commit=AsyncMock(),
            rollback=AsyncMock(),
            refresh=AsyncMock(),
        ),
        "find_by_owner_and_name": AsyncMock(return_value=None),
        "list_by_owner": AsyncMock(return_value=[]),
        "get_by_id": AsyncMock(return_value=None),
        "add": AsyncMock(),
        "delete": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _service(repository, storage=None, index=None) -> ProjectService:
    return ProjectService(
        repository,
        storage or Mock(),
        StorageLocationFactory(_storage_config()),
        index or AsyncMock(),
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

        async def assign_id(project: Project) -> Project:
            project.id = 12
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = assign_id
        index = AsyncMock()
        service = _service(repository, index=index)

        with patch.object(project_service_module, "logger") as logger:
            result = await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        created = repository.add.await_args.args[0]
        self.assertEqual("active", created.status)
        self.assertEqual("active", result.status)
        index.initialize.assert_awaited_once_with(created)
        self.assertEqual(2, repository.session.commit.await_count)
        self.assertIn("action=project.create", repr(logger.method_calls))
        self.assertNotIn("PM-Agent", repr(logger.method_calls))

    async def test_create_rejects_active_duplicate(self) -> None:
        """验证同一用户不能创建同名活跃项目。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 名称与已有活跃项目相同的 CreateProjectRequest。
        @Return: 抛出 PROJECT_NAME_EXISTS 的 AppException。
        """
        repository = _repository(
            find_by_owner_and_name=AsyncMock(return_value=_project())
        )
        service = _service(repository)

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(ErrorCode.PROJECT_NAME_EXISTS, caught.exception.error)
        repository.add.assert_not_awaited()

    async def test_create_retries_failed_initialization(self) -> None:
        """验证初始化失败的同名项目会复用原记录重试。

        @Param owner_user_id: 原项目所有者用户 ID。
        @Param request: 名称与 init_failed 项目相同的 CreateProjectRequest。
        @Return: 复用原项目 ID 且状态为 active 的 ProjectResponse。
        @SideEffect: 重新初始化索引并提交项目状态。
        """
        existing = _project(status="init_failed")
        repository = _repository(
            find_by_owner_and_name=AsyncMock(return_value=existing)
        )
        index = AsyncMock()
        service = _service(repository, index=index)

        result = await service.create(
            7,
            CreateProjectRequest(project_name="PM-Agent"),
        )

        self.assertEqual(12, result.id)
        self.assertEqual("active", result.status)
        index.initialize.assert_awaited_once_with(existing)
        repository.add.assert_not_awaited()
        repository.session.commit.assert_awaited_once()

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

    async def test_create_removes_record_when_index_initialization_fails(self) -> None:
        """验证索引初始化失败时清理未完成的项目记录。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param request: 合法且名称唯一的项目创建请求。
        @Return: 继续抛出索引初始化阶段的 AppException。
        @SideEffect: 删除已创建项目记录并提交清理事务。
        """
        repository = _repository()

        async def assign_id(project: Project) -> Project:
            project.id = 12
            project.created_at = datetime(2026, 7, 27, 9, 0, 0)
            project.updated_at = datetime(2026, 7, 27, 9, 0, 0)
            return project

        repository.add.side_effect = assign_id
        index = AsyncMock()
        expected = AppException(ErrorCode.PROJECT_INDEX_WRITE_FAILED)
        index.initialize.side_effect = expected
        service = _service(repository, index=index)

        with self.assertRaises(AppException) as caught:
            await service.create(
                7,
                CreateProjectRequest(project_name="PM-Agent"),
            )

        self.assertIs(expected, caught.exception)
        repository.delete.assert_awaited_once_with(12)
        self.assertEqual(2, repository.session.commit.await_count)

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
            (_project(status="init_failed"), ErrorCode.PROJECT_DISABLED),
        ]

        for project, expected_error in cases:
            with self.subTest(error=expected_error):
                repository = _repository(get_by_id=AsyncMock(return_value=project))
                service = _service(repository)
                with self.assertRaises(AppException) as caught:
                    await service.get_owned(7, 12)
                self.assertIs(expected_error, caught.exception.error)

    async def test_delete_owned_removes_storage_and_record(self) -> None:
        """验证删除项目会依次清理对象存储和数据库记录。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param project_id: 状态为 active 的项目 ID。
        @Return: None，操作成功完成。
        @SideEffect: 删除项目对象前缀、删除项目记录并提交事务。
        """
        project = _project()
        repository = _repository(get_by_id=AsyncMock(return_value=project))
        storage = Mock()
        service = _service(repository, storage=storage)

        await service.delete_owned(7, 12)

        storage.remove_prefix.assert_called_once()
        repository.delete.assert_awaited_once_with(12)
        repository.session.commit.assert_awaited_once()

    async def test_delete_owned_wraps_storage_failure(self) -> None:
        """验证对象存储清理失败时不删除数据库记录。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param project_id: 状态为 active 的项目 ID。
        @Return: 抛出 PROJECT_DELETE_FAILED 的 AppException。
        """
        repository = _repository(get_by_id=AsyncMock(return_value=_project()))
        storage = Mock()
        storage.remove_prefix.side_effect = AppException(ErrorCode.FILE_STORAGE_ERROR)
        service = _service(repository, storage=storage)

        with self.assertRaises(AppException) as caught:
            await service.delete_owned(7, 12)

        self.assertIs(ErrorCode.PROJECT_DELETE_FAILED, caught.exception.error)
        repository.delete.assert_not_awaited()

    async def test_delete_owned_rolls_back_database_failure(self) -> None:
        """验证项目记录删除失败时回滚数据库事务。

        @Param owner_user_id: 项目所有者用户 ID。
        @Param project_id: 状态为 active 的项目 ID。
        @Return: 抛出 PROJECT_DELETE_FAILED 的 AppException。
        @SideEffect: 对象存储已清理，数据库事务被回滚。
        """
        repository = _repository(
            get_by_id=AsyncMock(return_value=_project()),
            delete=AsyncMock(side_effect=RuntimeError("database failed")),
        )
        storage = Mock()
        service = _service(repository, storage=storage)

        with self.assertRaises(AppException) as caught:
            await service.delete_owned(7, 12)

        self.assertIs(ErrorCode.PROJECT_DELETE_FAILED, caught.exception.error)
        storage.remove_prefix.assert_called_once()
        repository.session.rollback.assert_awaited_once()
