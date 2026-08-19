"""项目文件仓储查询测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.modules.project_file.repository import ProjectFileRepository


class ProjectFileRepositoryTest(IsolatedAsyncioTestCase):
    async def test_parse_candidates_include_previous_analysis_version(self) -> None:
        session = SimpleNamespace(
            scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: []))
        )
        repository = ProjectFileRepository(session)

        result = await repository.list_parse_candidates(10, "file-detail-v2")

        self.assertEqual([], result)
        statement = session.scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("analysis_version IS NULL", sql)
        self.assertIn("analysis_version != 'file-detail-v2'", sql)
        self.assertIn("last_error_code IS NULL", sql)
        self.assertIn("upload_status = 'success'", sql)
