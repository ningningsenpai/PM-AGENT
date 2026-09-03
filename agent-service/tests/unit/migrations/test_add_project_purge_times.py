"""项目延迟物理清理字段迁移单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260903_02_add_project_purge_times.py"
    )
    spec = spec_from_file_location("add_project_purge_times_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AddProjectPurgeTimesRevisionTest(TestCase):
    def test_upgrade_adds_times_backfills_disabled_projects_and_indexes(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        columns = [call.args[1] for call in revision.op.add_column.call_args_list]
        self.assertEqual(["deleted_at", "purge_after"], [column.name for column in columns])
        self.assertTrue(all(column.nullable for column in columns))
        update_sql = str(revision.op.execute.call_args.args[0])
        self.assertIn("WHERE record_status = 'disabled'", update_sql)
        self.assertIn("INTERVAL 30 DAY", update_sql)
        revision.op.create_index.assert_called_once_with(
            "idx_project_record_purge",
            "pm_project",
            ["record_status", "purge_after"],
            unique=False,
        )
        self.assertEqual("20260903_01", revision.down_revision)

    def test_downgrade_removes_index_and_times(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.downgrade()

        revision.op.drop_index.assert_called_once_with(
            "idx_project_record_purge",
            table_name="pm_project",
        )
        self.assertEqual(
            ["purge_after", "deleted_at"],
            [call.args[1] for call in revision.op.drop_column.call_args_list],
        )
