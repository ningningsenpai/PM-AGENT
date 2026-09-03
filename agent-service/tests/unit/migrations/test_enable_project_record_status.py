"""项目记录状态与唯一约束迁移单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260903_01_enable_project_record_status.py"
    )
    spec = spec_from_file_location(
        "enable_project_record_status_revision", revision_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnableProjectRecordStatusRevisionTest(TestCase):
    def test_upgrade_replaces_status_values_and_unique_constraint(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        revision.op.alter_column.assert_called_once()
        alter_args, alter_kwargs = revision.op.alter_column.call_args
        self.assertEqual(("pm_project", "record_status"), alter_args)
        self.assertEqual(16, alter_kwargs["existing_type"].length)
        self.assertFalse(alter_kwargs["existing_nullable"])
        self.assertEqual("enabled", alter_kwargs["server_default"])
        added_column = revision.op.add_column.call_args.args[1]
        self.assertEqual("enabled_project_name", added_column.name)
        self.assertIsNotNone(added_column.computed)
        revision.op.create_unique_constraint.assert_called_once_with(
            "uk_project_owner_enabled_name",
            "pm_project",
            ["owner_user_id", "enabled_project_name"],
        )
        self.assertEqual("20260902_02", revision.down_revision)

    def test_downgrade_restores_old_constraint_without_duplicates(self) -> None:
        revision = _load_revision()
        revision.op = Mock()
        revision.op.get_bind.return_value.execute.return_value.first.return_value = None

        revision.downgrade()

        revision.op.create_unique_constraint.assert_called_once_with(
            "uk_project_owner_name",
            "pm_project",
            ["owner_user_id", "project_name"],
        )
        revision.op.drop_column.assert_called_once_with(
            "pm_project",
            "enabled_project_name",
        )
        revision.op.alter_column.assert_called_once()
        alter_args, alter_kwargs = revision.op.alter_column.call_args
        self.assertEqual(("pm_project", "record_status"), alter_args)
        self.assertEqual(16, alter_kwargs["existing_type"].length)
        self.assertFalse(alter_kwargs["existing_nullable"])
        self.assertEqual("active", alter_kwargs["server_default"])

    def test_downgrade_rejects_duplicate_project_history(self) -> None:
        revision = _load_revision()
        revision.op = Mock()
        revision.op.get_bind.return_value.execute.return_value.first.return_value = (
            7,
            "PM-Agent",
        )

        with self.assertRaisesRegex(RuntimeError, "无法恢复旧项目名称唯一约束"):
            revision.downgrade()

        revision.op.create_unique_constraint.assert_not_called()
