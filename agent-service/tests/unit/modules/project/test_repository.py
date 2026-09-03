"""项目数据访问单元测试。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.modules.project.repository import ProjectRepository


class ProjectRepositoryTest(IsolatedAsyncioTestCase):
    async def test_find_enabled_by_owner_and_name_excludes_disabled_records(
        self,
    ) -> None:
        """验证同名项目查询只返回参与业务的记录。"""
        scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: None))
        repository = ProjectRepository(SimpleNamespace(scalars=scalars))

        result = await repository.find_enabled_by_owner_and_name(7, "PM-Agent")

        self.assertIsNone(result)
        statement = scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project.owner_user_id = 7", sql)
        self.assertIn("pm_project.project_name = 'PM-Agent'", sql)
        self.assertIn("pm_project.record_status = 'enabled'", sql)

    async def test_list_by_owner_only_selects_enabled_records(self) -> None:
        """验证项目列表查询在数据库层排除惰性删除记录。"""
        scalars = AsyncMock(return_value=SimpleNamespace(all=list))
        repository = ProjectRepository(SimpleNamespace(scalars=scalars))

        result = await repository.list_by_owner(7)

        self.assertEqual([], result)
        statement = scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project.owner_user_id = 7", sql)
        self.assertIn("pm_project.record_status = 'enabled'", sql)

    async def test_list_purge_due_selects_expired_disabled_records(self) -> None:
        """验证物理清理查询只选择已经到期的禁用项目。"""
        scalars = AsyncMock(return_value=SimpleNamespace(all=list))
        repository = ProjectRepository(SimpleNamespace(scalars=scalars))
        now = datetime(2026, 10, 3, 10, 0, 0, tzinfo=UTC)

        result = await repository.list_purge_due(now)

        self.assertEqual([], result)
        statement = scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project.record_status = 'disabled'", sql)
        self.assertIn("pm_project.purge_after IS NOT NULL", sql)
        self.assertIn("pm_project.purge_after <=", sql)
        self.assertIn("ORDER BY pm_project.purge_after ASC", sql)

    async def test_delete_purge_due_rechecks_cleanup_conditions(self) -> None:
        """验证物理删除前再次检查记录状态和清理时间。"""
        execute = AsyncMock(return_value=SimpleNamespace(rowcount=1))
        repository = ProjectRepository(SimpleNamespace(execute=execute))
        now = datetime(2026, 10, 3, 10, 0, 0, tzinfo=UTC)

        deleted = await repository.delete_purge_due(12, now)

        self.assertTrue(deleted)
        statement = execute.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project.id = 12", sql)
        self.assertIn("pm_project.record_status = 'disabled'", sql)
        self.assertIn("pm_project.purge_after IS NOT NULL", sql)
        self.assertIn("pm_project.purge_after <=", sql)
