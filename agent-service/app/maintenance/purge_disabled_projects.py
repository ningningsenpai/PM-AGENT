"""清理超过保留期的已删除项目。"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.infrastructure.database import get_session_factory
from app.infrastructure.storage import StorageLocationFactory, get_object_storage
from app.modules.project.purge_service import ProjectPurgeService, ProjectPurgeSummary
from app.modules.project.repository import ProjectRepository


async def _run_command() -> ProjectPurgeSummary:
    settings = get_settings()
    storage = get_object_storage()
    locations = StorageLocationFactory(settings.storage)
    async with get_session_factory()() as session:
        service = ProjectPurgeService(
            ProjectRepository(session),
            storage,
            locations,
        )
        return await service.run_once()


def main() -> int:
    try:
        summary = asyncio.run(_run_command())
    except Exception as exception:  # noqa: BLE001
        print(f"项目清理任务失败：{exception}", file=sys.stderr)
        return 1
    print(summary.to_json())
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
