"""雪花 ID Alembic revision 单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, call


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260902_02_enable_snowflake_ids.py"
    )
    spec = spec_from_file_location("enable_snowflake_ids_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnableSnowflakeIdsRevisionTest(TestCase):
    def test_upgrade_disables_database_auto_increment(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        self.assertEqual(
            [call("pm_project", "id"), call("pm_user", "id")],
            [call(*item.args[:2]) for item in revision.op.alter_column.call_args_list],
        )
        for item in revision.op.alter_column.call_args_list:
            self.assertFalse(item.kwargs["autoincrement"])
        self.assertEqual(2, revision.op.drop_constraint.call_count)
        self.assertEqual(2, revision.op.create_foreign_key.call_count)
        self.assertEqual("20260902_01", revision.down_revision)

    def test_downgrade_restores_database_auto_increment(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.downgrade()

        for item in revision.op.alter_column.call_args_list:
            self.assertTrue(item.kwargs["autoincrement"])
        self.assertEqual(2, revision.op.drop_constraint.call_count)
        self.assertEqual(2, revision.op.create_foreign_key.call_count)
