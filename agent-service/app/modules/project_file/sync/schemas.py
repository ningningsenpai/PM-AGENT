"""项目文件同步规划请求与响应。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.project_file.sync.domain import (
    AmbiguousFileAction,
    LocalFileSnapshot,
    MatchedFileAction,
    ProjectFileSyncPlan,
    RejectedFileSnapshot,
    RemoteFileSnapshot,
)


class SyncSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ProjectFileManifestItem(SyncSchema):
    """单文件元信息"""
    relative_path: str
    size_bytes: int
    source_mtime_ms: int
    content_hash: str | None = None
    content_type: str | None = None


class ProjectFileSyncPlanRequest(SyncSchema):
    """前端传递项目文件信息汇总。"""
    snapshot_complete: bool
    scope: Literal["project"]
    items: list[ProjectFileManifestItem]


class SyncLocalFile(SyncSchema):
    relative_path: str
    size_bytes: int
    source_mtime_ms: int
    content_hash: str
    content_type: str


class SyncRemoteFile(SyncSchema):
    remote_file_id: int
    remote_relative_path: str
    remote_size_bytes: int
    remote_source_mtime_ms: int
    remote_content_hash: str
    remote_content_type: str
    lock_version: int
    remote_status: str
    remote_upload_status: str


class SyncMatchedAction(SyncLocalFile, SyncRemoteFile):
    pass


class SyncAddedAction(SyncLocalFile):
    pass


class SyncDeletedAction(SyncRemoteFile):
    pass


class SyncRejectedAction(SyncSchema):
    relative_path: str
    error_code: str
    error_message: str
    remote_file_id: int | None = None
    remote_relative_path: str | None = None
    lock_version: int | None = None


class SyncAmbiguousAction(SyncSchema):
    content_hash: str
    local_items: list[SyncLocalFile]
    remote_items: list[SyncRemoteFile]


class ProjectFileSyncPlanResponse(SyncSchema):
    snapshot_complete: bool
    scope: Literal["project"] = "project"
    unchanged: list[SyncMatchedAction]
    modified: list[SyncMatchedAction]
    moved: list[SyncMatchedAction]
    added: list[SyncAddedAction]
    deleted: list[SyncDeletedAction]
    rejected: list[SyncRejectedAction]
    ambiguous: list[SyncAmbiguousAction]


def to_sync_plan_response(
    plan: ProjectFileSyncPlan,
    *,
    snapshot_complete: bool,
) -> ProjectFileSyncPlanResponse:
    return ProjectFileSyncPlanResponse(
        snapshot_complete=snapshot_complete,
        unchanged=[_matched_action(item) for item in plan.unchanged],
        modified=[_matched_action(item) for item in plan.modified],
        moved=[_matched_action(item) for item in plan.moved],
        added=[_local_action(SyncAddedAction, item) for item in plan.added],
        deleted=[_remote_action(SyncDeletedAction, item) for item in plan.deleted],
        rejected=[_rejected_action(item) for item in plan.rejected],
        ambiguous=[_ambiguous_action(item) for item in plan.ambiguous],
    )


def _matched_action(item: MatchedFileAction) -> SyncMatchedAction:
    return SyncMatchedAction(
        **_local_values(item.local_file),
        **_remote_values(item.remote_file),
    )


def _local_action(model, item: LocalFileSnapshot):
    return model(**_local_values(item))


def _remote_action(model, item: RemoteFileSnapshot):
    return model(**_remote_values(item))


def _rejected_action(item: RejectedFileSnapshot) -> SyncRejectedAction:
    remote = item.remote_file
    return SyncRejectedAction(
        relative_path=item.relative_path,
        error_code=item.error_code,
        error_message=item.error_message,
        remote_file_id=remote.file_id if remote else None,
        remote_relative_path=remote.relative_path if remote else None,
        lock_version=remote.lock_version if remote else None,
    )


def _ambiguous_action(item: AmbiguousFileAction) -> SyncAmbiguousAction:
    return SyncAmbiguousAction(
        content_hash=item.content_hash,
        local_items=[_local_action(SyncLocalFile, file) for file in item.local_files],
        remote_items=[
            _remote_action(SyncRemoteFile, file) for file in item.remote_files
        ],
    )


def _local_values(item: LocalFileSnapshot) -> dict:
    return {
        "relative_path": item.relative_path,
        "size_bytes": item.size_bytes,
        "source_mtime_ms": item.source_mtime_ms,
        "content_hash": item.content_hash,
        "content_type": item.content_type,
    }


def _remote_values(item: RemoteFileSnapshot) -> dict:
    return {
        "remote_file_id": item.file_id,
        "remote_relative_path": item.relative_path,
        "remote_size_bytes": item.size_bytes,
        "remote_source_mtime_ms": item.source_mtime_ms,
        "remote_content_hash": item.content_hash,
        "remote_content_type": item.content_type,
        "lock_version": item.lock_version,
        "remote_status": item.status,
        "remote_upload_status": item.upload_status,
    }
