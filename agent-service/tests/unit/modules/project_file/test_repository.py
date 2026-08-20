"""项目文件仓储查询测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.modules.project_file.repository import ProjectFileRepository


class ProjectFileRepositoryTest(IsolatedAsyncioTestCase):
    async def test_analysis_candidates_require_missing_detail_and_retry_budget(
        self,
    ) -> None:
        session = SimpleNamespace(
            scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: []))
        )
        repository = ProjectFileRepository(session)

        result = await repository.list_analysis_candidates(10)

        self.assertEqual([], result)
        statement = session.scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("detail_ref IS NULL", sql)
        self.assertIn("parse_attempts < 3", sql)
        self.assertIn("upload_status = 'success'", sql)

    async def test_force_analysis_candidates_ignore_detail_and_retry_budget(
        self,
    ) -> None:
        session = SimpleNamespace(
            scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: []))
        )
        repository = ProjectFileRepository(session)

        result = await repository.list_analysis_candidates(10, force=True)

        self.assertEqual([], result)
        statement = session.scalars.await_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertNotIn("detail_ref IS NULL", sql)
        self.assertNotIn("parse_attempts <", sql)
        self.assertIn("status = 'active'", sql)
        self.assertIn("upload_status = 'success'", sql)
        self.assertIn("business_code != 'system'", sql)

    async def test_analysis_success_uses_lock_version_compare_and_swap(self) -> None:
        session = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(rowcount=1))
        )
        repository = ProjectFileRepository(session)
        detail = SimpleNamespace(
            detail_ref="system/file_details/detail.json",
            module="backend",
            kind="source",
            file_type="code",
            language="python",
            importance="high",
            summary="后端入口",
            keywords=["FastAPI"],
        )

        updated = await repository.record_analysis_success(
            10,
            30,
            "content-hash",
            4,
            detail,
        )

        self.assertTrue(updated)
        statement = session.execute.await_args.args[0]
        compiled = statement.compile()
        sql = str(compiled)
        self.assertIn("pm_project_file.content_hash =", sql)
        self.assertIn("pm_project_file.lock_version =", sql)
        self.assertIn(4, compiled.params.values())
        self.assertNotIn("lock_version", sql.split(" WHERE ", maxsplit=1)[0])

    async def test_analysis_failure_preserves_detail_and_uses_cas(self) -> None:
        session = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(rowcount=0))
        )
        repository = ProjectFileRepository(session)

        updated = await repository.record_analysis_failure(
            10,
            30,
            "content-hash",
            7,
            "MODEL_FAILED",
            "模型调用失败",
        )

        self.assertFalse(updated)
        statement = session.execute.await_args.args[0]
        compiled = statement.compile()
        sql = str(compiled)
        self.assertIn("pm_project_file.content_hash =", sql)
        self.assertIn("pm_project_file.lock_version =", sql)
        self.assertIn(7, compiled.params.values())
        set_clause = sql.split(" WHERE ", maxsplit=1)[0]
        self.assertNotIn("lock_version", set_clause)
        for preserved_field in (
            "detail_ref",
            "module",
            "kind",
            "file_type",
            "language",
            "importance",
            "summary",
            "keywords",
        ):
            self.assertNotIn(preserved_field, set_clause)
