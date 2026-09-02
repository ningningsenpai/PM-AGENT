"""项目数据访问单元测试。"""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.modules.project.repository import ProjectRepository


class ProjectRepositoryTest(IsolatedAsyncioTestCase):
    async def test_list_by_owner_only_selects_active_records(self) -> None:
        """验证项目列表查询在数据库层排除惰性删除记录。"""
        scalars = AsyncMock(return_value=SimpleNamespace(all=list))
        repository = ProjectRepository(SimpleNamespace(scalars=scalars))

        result = await repository.list_by_owner(7)

        self.assertEqual([], result)
        statement = scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("pm_project.owner_user_id = 7", sql)
        self.assertIn("pm_project.record_status = 'active'", sql)
