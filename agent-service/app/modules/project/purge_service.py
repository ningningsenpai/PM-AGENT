"""到期项目物理清理服务。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime

from app.core.logger import get_logger
from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.modules.project.repository import ProjectRepository

logger = get_logger(__name__)


@dataclass(slots=True)
class ProjectPurgeSummary:
    scanned: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class ProjectPurgeService:
    """按项目依次清理 MinIO 对象和到期数据库记录。"""

    def __init__(
        self,
        repository: ProjectRepository,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._locations = locations

    async def run_once(self) -> ProjectPurgeSummary:
        now = datetime.now()  # noqa: DTZ005
        projects = await self._repository.list_purge_due(now)
        await self._repository.session.commit()
        summary = ProjectPurgeSummary(scanned=len(projects))

        for project in projects:
            try:
                location = self._locations.project_prefix(
                    project.owner_user_id,
                    project.id,
                )
                await asyncio.to_thread(self._storage.remove_prefix, location)
                remaining = await asyncio.to_thread(
                    self._storage.list_prefix,
                    location,
                )
                if remaining:
                    summary.failed += 1
                    logger.error(
                        "项目对象未完全删除，跳过数据库清理 "
                        "action=project.purge stage=storage_verify "
                        "userId=%s projectId=%s remaining=%s",
                        project.owner_user_id,
                        project.id,
                        len(remaining),
                    )
                    continue

                deleted = await self._repository.delete_purge_due(project.id, now)
                await self._repository.session.commit()
                if deleted:
                    summary.succeeded += 1
                else:
                    summary.skipped += 1
            except Exception:
                await self._repository.session.rollback()
                summary.failed += 1
                logger.exception(
                    "项目清理失败，等待下次定时任务处理 "
                    "action=project.purge userId=%s projectId=%s",
                    project.owner_user_id,
                    project.id,
                )

        logger.info(
            "项目清理完成 action=project.purge scanned=%s succeeded=%s "
            "skipped=%s failed=%s",
            summary.scanned,
            summary.succeeded,
            summary.skipped,
            summary.failed,
        )
        return summary
