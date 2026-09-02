"""项目记录状态 Alembic revision 单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260902_01_add_project_record_status.py"
    )
    spec = spec_from_file_location("add_project_record_status_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AddProjectRecordStatusRevisionTest(TestCase):
    def test_upgrade_adds_status_constraint_and_index(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        revision.op.add_column.assert_called_once()
        table_name, column = revision.op.add_column.call_args.args
        self.assertEqual("pm_project", table_name)
        self.assertEqual("record_status", column.name)
        self.assertFalse(column.nullable)
        self.assertEqual("active", column.server_default.arg)
        revision.op.create_check_constraint.assert_called_once_with(
            "ck_project_record_status",
            "pm_project",
            "record_status IN ('active', 'inactive')",
        )
        revision.op.create_index.assert_called_once_with(
            "idx_project_owner_record_status",
            "pm_project",
            ["owner_user_id", "record_status"],
            unique=False,
        )
        self.assertEqual("20260820_01", revision.down_revision)

    def test_downgrade_removes_status_index_constraint_and_column(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.downgrade()

        revision.op.drop_index.assert_called_once_with(
            "idx_project_owner_record_status",
            table_name="pm_project",
        )
        revision.op.drop_constraint.assert_called_once_with(
            "ck_project_record_status",
            "pm_project",
            type_="check",
        )
        revision.op.drop_column.assert_called_once_with(
            "pm_project",
            "record_status",
        )
