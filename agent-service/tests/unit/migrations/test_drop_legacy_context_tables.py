"""旧 Context 表清理 revision 单元测试。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, call


def _load_revision():
    revision_path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260910_02_drop_legacy_context_tables.py"
    )
    spec = spec_from_file_location("drop_legacy_context_tables_revision", revision_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Alembic revision")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DropLegacyContextTablesRevisionTest(TestCase):
    def test_upgrade_drops_tables_in_foreign_key_order(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.upgrade()

        self.assertEqual(
            [
                call("agent_context_change"),
                call("agent_context_entry"),
                call("agent_context_scope"),
            ],
            revision.op.drop_table.call_args_list,
        )
        self.assertEqual("20260910_01", revision.down_revision)
        self.assertEqual("20260910_02", revision.revision)

    def test_downgrade_restores_tables_and_indexes(self) -> None:
        revision = _load_revision()
        revision.op = Mock()

        revision.downgrade()

        self.assertEqual(
            [
                "agent_context_scope",
                "agent_context_entry",
                "agent_context_change",
            ],
            [item.args[0] for item in revision.op.create_table.call_args_list],
        )
        self.assertEqual(
            ["ix_entry_scope_status", "ix_change_entry_version"],
            [item.args[0] for item in revision.op.create_index.call_args_list],
        )
