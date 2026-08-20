"""删除 analysis_version Alembic revision 单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260820_01_remove_project_file_analysis_version.py"
    )
    spec = spec_from_file_location("remove_analysis_version_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RemoveAnalysisVersionRevisionTest(TestCase):
    def test_upgrade_only_drops_legacy_column(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        revision.op.drop_column.assert_called_once_with(
            "pm_project_file",
            "analysis_version",
        )
        self.assertEqual("20260724_01", revision.down_revision)

    def test_downgrade_restores_nullable_string_column(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.downgrade()

        revision.op.add_column.assert_called_once()
        table_name, column = revision.op.add_column.call_args.args
        self.assertEqual("pm_project_file", table_name)
        self.assertEqual("analysis_version", column.name)
        self.assertEqual(64, column.type.length)
        self.assertTrue(column.nullable)
