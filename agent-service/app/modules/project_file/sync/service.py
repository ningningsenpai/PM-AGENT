"""项目文件同步规划服务。"""

from __future__ import annotations

from collections import Counter

from app.core.config import FileConfig
from app.core.errors import AppException, ErrorCode
from app.modules.project.service import ProjectService
from app.modules.project_file.domain import FileBusinessType
from app.modules.project_file.repository import ProjectFileRepository
from app.modules.project_file.sync.domain import (
    LocalFileSnapshot,
    ProjectFileSyncPlanner,
    RejectedFileSnapshot,
    RemoteFileSnapshot,
    prepare_local_snapshot,
)
from app.modules.project_file.sync.schemas import (
    ProjectFileSyncPlanRequest,
    ProjectFileSyncPlanResponse,
    to_sync_plan_response,
)


class ProjectFileSyncService:
    def __init__(
        self,
        repository: ProjectFileRepository,
        projects: ProjectService,
        planner: ProjectFileSyncPlanner,
        file_config: FileConfig,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._planner = planner
        self._file_config = file_config

    async def plan(
        self,
        user_id: int,
        project_id: int,
        request: ProjectFileSyncPlanRequest,
    ) -> ProjectFileSyncPlanResponse:
        await self._projects.require_owned(user_id, project_id)
        remote_files = await self._repository.list(
            project_id,
            FileBusinessType.PROJECT.value,
        )
        local_files, rejected_files = self._prepare_local_files(request)
        plan = self._planner.plan(
            local_files,
            [self._remote_snapshot(file) for file in remote_files],
            rejected_files,
            snapshot_complete=request.snapshot_complete,
        )
        return to_sync_plan_response(
            plan,
            snapshot_complete=request.snapshot_complete,
        )

    def _prepare_local_files(
        self,
        request: ProjectFileSyncPlanRequest,
    ) -> tuple[list[LocalFileSnapshot], list[RejectedFileSnapshot]]:
        """
        根据后端的文件筛选逻辑再进行一次文件筛选
        符合规则且流程正确 -> 进入 List[prepared]
        不符合规则 -> 进入 List[rejected]
        """
        prepared: list[LocalFileSnapshot] = []
        rejected: list[RejectedFileSnapshot] = []
        for item in request.items:
            try:
                prepared.append(
                    prepare_local_snapshot(
                        item.relative_path,
                        item.size_bytes,
                        item.source_mtime_ms,
                        item.content_hash,
                        item.content_type,
                        self._file_config,
                    )
                )
            except AppException as exception:
                rejected.append(
                    RejectedFileSnapshot(
                        relative_path=self._safe_normalize_path(item.relative_path),
                        error_code=exception.error.name,
                        error_message=exception.message,
                    )
                )

        duplicate_paths = {
            path
            for path, count in Counter(file.relative_path for file in prepared).items()
            if count > 1
        }
        if duplicate_paths:
            prepared = [
                file for file in prepared if file.relative_path not in duplicate_paths
            ]
            rejected.extend(
                RejectedFileSnapshot(
                    relative_path=path,
                    error_code=ErrorCode.PARAM_INVALID.name,
                    error_message="同步清单中存在重复文件路径",
                )
                for path in sorted(duplicate_paths)
            )
        return prepared, rejected

    @staticmethod
    def _safe_normalize_path(relative_path: str) -> str:
        from app.modules.project_file.management.domain import normalize_relative_path

        try:
            return normalize_relative_path(relative_path)
        except AppException:
            return relative_path.strip().replace("\\", "/")

    @staticmethod
    def _remote_snapshot(file) -> RemoteFileSnapshot:
        """构建服务端已存在的文件元信息列表"""
        return RemoteFileSnapshot(
            file_id=file.id,
            relative_path=file.relative_path,
            size_bytes=file.size_bytes,
            source_mtime_ms=file.source_mtime_ms,
            content_hash=file.content_hash,
            content_type=file.content_type,
            lock_version=file.lock_version,
            status=file.status,
            upload_status=file.upload_status,
        )
