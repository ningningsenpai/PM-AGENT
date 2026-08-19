"""项目文件同步规划服务测试。"""

from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.modules.project_file.sync.domain import ProjectFileSyncPlanner
from app.modules.project_file.sync.schemas import ProjectFileSyncPlanRequest
from app.modules.project_file.sync.service import ProjectFileSyncService
from tests.unit.modules.project_file.factories import project_file
from tests.unit.modules.project_file.management.factories import file_config


def _service(remote_files):
    repository = AsyncMock()
    repository.list.return_value = remote_files
    projects = AsyncMock()
    service = ProjectFileSyncService(
        repository,
        projects,
        ProjectFileSyncPlanner(),
        file_config(),
    )
    return service, repository, projects


class ProjectFileSyncServiceTest(IsolatedAsyncioTestCase):
    async def test_authorizes_and_builds_camel_case_response(self) -> None:
        remote = project_file(content=b"same")
        service, repository, projects = _service([remote])
        request = ProjectFileSyncPlanRequest.model_validate(
            {
                "snapshotComplete": True,
                "scope": "project",
                "items": [
                    {
                        "relativePath": "docs/README.md",
                        "sizeBytes": 4,
                        "sourceMtimeMs": 200,
                        "contentHash": remote.content_hash,
                        "contentType": "text/markdown",
                    }
                ],
            }
        )

        response = await service.plan(1, 10, request)
        payload = response.model_dump(mode="json", by_alias=True)

        projects.require_owned.assert_awaited_once_with(1, 10)
        repository.list.assert_awaited_once_with(10, "project")
        self.assertEqual(30, payload["unchanged"][0]["remoteFileId"])
        self.assertEqual(0, payload["unchanged"][0]["lockVersion"])
        self.assertEqual("project", payload["scope"])

    async def test_returns_rejection_and_preserves_matching_remote(self) -> None:
        remote = project_file(relative_path=".env", file_name=".env")
        service, _, _ = _service([remote])
        request = ProjectFileSyncPlanRequest(
            snapshot_complete=True,
            scope="project",
            items=[
                {
                    "relative_path": ".env",
                    "size_bytes": 10,
                    "source_mtime_ms": 100,
                    "content_hash": remote.content_hash,
                    "content_type": "text/plain",
                }
            ],
        )

        response = await service.plan(1, 10, request)

        self.assertEqual([], response.deleted)
        self.assertEqual("FILE_PATH_IGNORED", response.rejected[0].error_code)
        self.assertEqual(remote.id, response.rejected[0].remote_file_id)

    async def test_rejects_duplicate_paths_without_deleting_remote(self) -> None:
        remote = project_file()
        service, _, _ = _service([remote])
        item = {
            "relative_path": "docs/README.md",
            "size_bytes": 10,
            "source_mtime_ms": 100,
            "content_hash": remote.content_hash,
            "content_type": "text/markdown",
        }
        request = ProjectFileSyncPlanRequest(
            snapshot_complete=True,
            scope="project",
            items=[item, item],
        )

        response = await service.plan(1, 10, request)

        self.assertEqual([], response.deleted)
        self.assertEqual("PARAM_INVALID", response.rejected[0].error_code)
        self.assertEqual(remote.id, response.rejected[0].remote_file_id)

    async def test_rejects_missing_hash_and_preserves_matching_remote(self) -> None:
        remote = project_file()
        service, _, _ = _service([remote])
        request = ProjectFileSyncPlanRequest(
            snapshot_complete=True,
            scope="project",
            items=[
                {
                    "relative_path": remote.relative_path,
                    "size_bytes": remote.size_bytes,
                    "source_mtime_ms": remote.source_mtime_ms,
                    "content_hash": None,
                    "content_type": remote.content_type,
                }
            ],
        )

        response = await service.plan(1, 10, request)

        self.assertEqual([], response.added)
        self.assertEqual([], response.modified)
        self.assertEqual([], response.deleted)
        self.assertEqual("PARAM_INVALID", response.rejected[0].error_code)
        self.assertEqual(
            "未提供可用于同步规划的文件内容哈希",
            response.rejected[0].error_message,
        )
        self.assertEqual(remote.id, response.rejected[0].remote_file_id)
