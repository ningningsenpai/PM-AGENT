"""到期项目物理清理服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.modules.project.purge_service import ProjectPurgeService


def _project(project_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=project_id, owner_user_id=7)


def _repository(projects: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        session=SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()),
        list_purge_due=AsyncMock(return_value=projects),
        delete_purge_due=AsyncMock(return_value=True),
    )


def _service(repository, storage) -> ProjectPurgeService:
    locations = StorageLocationFactory(SimpleNamespace(bucket="pm-agent-test"))
    return ProjectPurgeService(repository, storage, locations)


class ProjectPurgeServiceTest(IsolatedAsyncioTestCase):
    async def test_run_once_removes_storage_before_database_record(self) -> None:
        """验证 MinIO 清空并确认后才物理删除项目记录。"""
        repository = _repository([_project(12)])
        storage = SimpleNamespace(remove_prefix=Mock(), list_prefix=Mock(return_value=[]))
        events: list[str] = []
        storage.remove_prefix.side_effect = lambda _location: events.append("remove")
        storage.list_prefix.side_effect = lambda _location: events.append("verify") or []

        async def delete_purge_due(_project_id, _now):
            events.append("database")
            return True

        repository.delete_purge_due.side_effect = delete_purge_due

        summary = await _service(repository, storage).run_once()

        self.assertEqual(["remove", "verify", "database"], events)
        self.assertEqual(1, summary.scanned)
        self.assertEqual(1, summary.succeeded)
        self.assertEqual(0, summary.failed)
        self.assertEqual(2, repository.session.commit.await_count)
        repository.session.rollback.assert_not_awaited()

    async def test_run_once_skips_database_when_objects_remain(self) -> None:
        """验证 MinIO 前缀仍有对象时保留数据库记录。"""
        repository = _repository([_project(12)])
        storage = SimpleNamespace(
            remove_prefix=Mock(),
            list_prefix=Mock(
                return_value=[StorageLocation("pm-agent-test", "PM-AGENT/7/12/a")]
            ),
        )

        summary = await _service(repository, storage).run_once()

        self.assertEqual(1, summary.failed)
        repository.delete_purge_due.assert_not_awaited()
        repository.session.commit.assert_awaited_once()

    async def test_run_once_continues_after_storage_failure(self) -> None:
        """验证单个项目 MinIO 删除失败后继续处理下一个项目。"""
        repository = _repository([_project(12), _project(13)])

        def remove_prefix(location: StorageLocation) -> None:
            if location.object_key.endswith("/12/"):
                raise RuntimeError("MinIO 删除失败")

        storage = SimpleNamespace(
            remove_prefix=Mock(side_effect=remove_prefix),
            list_prefix=Mock(return_value=[]),
        )

        summary = await _service(repository, storage).run_once()

        self.assertEqual(2, summary.scanned)
        self.assertEqual(1, summary.succeeded)
        self.assertEqual(1, summary.failed)
        repository.delete_purge_due.assert_awaited_once()
        self.assertEqual(13, repository.delete_purge_due.await_args.args[0])
        repository.session.rollback.assert_awaited_once()

    async def test_run_once_continues_after_database_failure(self) -> None:
        """验证单个项目 MySQL 删除失败后回滚并继续处理。"""
        repository = _repository([_project(12), _project(13)])
        repository.delete_purge_due.side_effect = [
            RuntimeError("MySQL 删除失败"),
            True,
        ]
        storage = SimpleNamespace(remove_prefix=Mock(), list_prefix=Mock(return_value=[]))

        summary = await _service(repository, storage).run_once()

        self.assertEqual(1, summary.succeeded)
        self.assertEqual(1, summary.failed)
        self.assertEqual(2, repository.delete_purge_due.await_count)
        repository.session.rollback.assert_awaited_once()
        self.assertEqual(2, repository.session.commit.await_count)
