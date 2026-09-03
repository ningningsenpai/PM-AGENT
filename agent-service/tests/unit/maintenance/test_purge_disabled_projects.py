"""到期项目清理命令单元测试。"""

from unittest import TestCase
from unittest.mock import AsyncMock, patch

from app.maintenance.purge_disabled_projects import main
from app.modules.project.purge_service import ProjectPurgeSummary


class PurgeDisabledProjectsCommandTest(TestCase):
    def test_main_returns_nonzero_when_any_project_failed(self) -> None:
        summary = ProjectPurgeSummary(scanned=2, succeeded=1, failed=1)
        with patch(
            "app.maintenance.purge_disabled_projects._run_command",
            new=AsyncMock(return_value=summary),
        ):
            exit_code = main()

        self.assertEqual(1, exit_code)

    def test_main_returns_nonzero_when_scan_fails(self) -> None:
        with patch(
            "app.maintenance.purge_disabled_projects._run_command",
            new=AsyncMock(side_effect=RuntimeError("数据库不可用")),
        ):
            exit_code = main()

        self.assertEqual(1, exit_code)
