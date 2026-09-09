"""项目文件分析 API 单元测试。"""

from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.core.security import AuthPrincipal
from app.modules.project_file.analysis.api import initialize_project_file_analysis


class ProjectFileAnalysisApiTest(IsolatedAsyncioTestCase):
    async def test_initialize_forwards_force_query_parameter(self) -> None:
        service = AsyncMock()
        result = {"status": "success"}
        service.analyze_pending_files.return_value = result

        response = await initialize_project_file_analysis(
            project_id=10,
            force=True,
            idempotency_key="parse-api-request",
            principal=AuthPrincipal(user_id=7, jti="session-jti"),
            service=service,
        )

        service.analyze_pending_files.assert_awaited_once_with(
            7,
            10,
            "parse-api-request",
            force=True,
        )
        self.assertIs(result, response.data)
