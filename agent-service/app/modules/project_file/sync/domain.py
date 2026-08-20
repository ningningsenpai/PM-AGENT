"""项目文件同步差异的纯计算。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import mimetypes
import re
from pathlib import PurePosixPath

from app.core.config import FileConfig
from app.core.errors import AppException, ErrorCode
from app.modules.project_file.management.domain import (
    file_extension,
    normalize_relative_path,
    validate_extension,
    validate_path,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class LocalFileSnapshot:
    """本地文件快照，用于与服务端进行比较。"""
    relative_path: str
    size_bytes: int
    source_mtime_ms: int
    content_hash: str
    content_type: str


@dataclass(frozen=True, slots=True)
class RemoteFileSnapshot:
    """服务端已经存在的对象快照，用于与本地快照进行匹配。"""
    file_id: int
    relative_path: str
    size_bytes: int
    source_mtime_ms: int
    content_hash: str
    content_type: str
    lock_version: int
    status: str
    upload_status: str


@dataclass(frozen=True, slots=True)
class RejectedFileSnapshot:
    """被拒绝文件具体情况"""
    relative_path: str
    error_code: str
    error_message: str
    remote_file: RemoteFileSnapshot | None = None


@dataclass(frozen=True, slots=True)
class MatchedFileAction:
    local_file: LocalFileSnapshot
    remote_file: RemoteFileSnapshot


@dataclass(frozen=True, slots=True)
class AmbiguousFileAction:
    content_hash: str
    local_files: tuple[LocalFileSnapshot, ...]
    remote_files: tuple[RemoteFileSnapshot, ...]


@dataclass(frozen=True, slots=True)
class ProjectFileSyncPlan:
    unchanged: tuple[MatchedFileAction, ...]
    modified: tuple[MatchedFileAction, ...]
    moved: tuple[MatchedFileAction, ...]
    added: tuple[LocalFileSnapshot, ...]
    deleted: tuple[RemoteFileSnapshot, ...]
    rejected: tuple[RejectedFileSnapshot, ...]
    ambiguous: tuple[AmbiguousFileAction, ...]


def prepare_local_snapshot(
    relative_path: str,
    size_bytes: int,
    source_mtime_ms: int,
    content_hash: str | None,
    supplied_content_type: str | None,
    config: FileConfig,
) -> LocalFileSnapshot:
    """规范化并校验浏览器上报的文件元数据。"""
    normalized_path = normalize_relative_path(relative_path)
    file_name = PurePosixPath(normalized_path).name
    extension = file_extension(file_name)
    validate_path(normalized_path, config)
    validate_extension(extension, config)
    if size_bytes <= 0:
        raise AppException(ErrorCode.PARAM_INVALID, "文件大小必须大于0")
    if size_bytes > config.max_size_bytes:
        raise AppException(ErrorCode.FILE_TOO_LARGE)
    if source_mtime_ms < 0:
        raise AppException(ErrorCode.PARAM_INVALID, "源文件修改时间不能小于0")

    guessed_type = mimetypes.guess_type(file_name)[0]
    normalized_content_type = (
        supplied_content_type or guessed_type or "application/octet-stream"
    ).lower()
    if normalized_content_type in config.blocked_mime_types:
        raise AppException(ErrorCode.FILE_MIME_TYPE_BLOCKED)

    if not content_hash or not content_hash.strip():
        raise AppException(
            ErrorCode.PARAM_INVALID,
            "未提供可用于同步规划的文件内容哈希",
        )
    normalized_hash = content_hash.strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized_hash):
        raise AppException(ErrorCode.PARAM_INVALID, "文件内容哈希必须是64位SHA-256")
    return LocalFileSnapshot(
        relative_path=normalized_path,
        size_bytes=size_bytes,
        source_mtime_ms=source_mtime_ms,
        content_hash=normalized_hash,
        content_type=normalized_content_type,
    )


class ProjectFileSyncPlanner:
    """根据本地完整清单和数据库快照生成无副作用同步计划。"""

    def plan(
        self,
        local_files: list[LocalFileSnapshot],
        remote_files: list[RemoteFileSnapshot],
        rejected_files: list[RejectedFileSnapshot],
        *,
        snapshot_complete: bool,
    ) -> ProjectFileSyncPlan:
        """
        将 local_files 和 remote_files 作为输入，生成下面七种状态的 tuple
        unchanged: 未改变
        modified: 文件内容修改
        moved: 文件路径改变
        added: 新增
        deleted: 删除
        rejected: 拒绝
        ambiguous: 未知文件
        """
        remote_by_path = {file.relative_path: file for file in remote_files}
        remaining_remote = dict(remote_by_path)
        remaining_local: dict[str, LocalFileSnapshot] = {}
        unchanged: list[MatchedFileAction] = []
        modified: list[MatchedFileAction] = []

        for local_file in local_files:
            remote_file = remaining_remote.pop(local_file.relative_path, None)
            if remote_file is None:
                remaining_local[local_file.relative_path] = local_file
                continue
            action = MatchedFileAction(local_file, remote_file)
            if (
                local_file.content_hash == remote_file.content_hash
                and self._is_healthy_remote(remote_file)
            ):
                unchanged.append(action)
            else:
                modified.append(action)

        enriched_rejected: list[RejectedFileSnapshot] = []
        for rejected_file in rejected_files:
            remote_file = remaining_remote.pop(rejected_file.relative_path, None)
            enriched_rejected.append(
                RejectedFileSnapshot(
                    relative_path=rejected_file.relative_path,
                    error_code=rejected_file.error_code,
                    error_message=rejected_file.error_message,
                    remote_file=remote_file,
                )
            )

        local_by_hash = self._group_local_by_hash(remaining_local.values())
        remote_by_hash = self._group_remote_by_hash(remaining_remote.values())
        moved: list[MatchedFileAction] = []
        ambiguous: list[AmbiguousFileAction] = []

        for content_hash in sorted(local_by_hash.keys() & remote_by_hash.keys()):
            local_group = local_by_hash[content_hash]
            remote_group = remote_by_hash[content_hash]
            if len(local_group) == 1 and len(remote_group) == 1:
                local_file = local_group[0]
                remote_file = remote_group[0]
                moved.append(MatchedFileAction(local_file, remote_file))
            else:
                ambiguous.append(
                    AmbiguousFileAction(
                        content_hash=content_hash,
                        local_files=tuple(local_group),
                        remote_files=tuple(remote_group),
                    )
                )
            for local_file in local_group:
                remaining_local.pop(local_file.relative_path, None)
            for remote_file in remote_group:
                remaining_remote.pop(remote_file.relative_path, None)

        return ProjectFileSyncPlan(
            unchanged=tuple(sorted(unchanged, key=self._matched_sort_key)),
            modified=tuple(sorted(modified, key=self._matched_sort_key)),
            moved=tuple(sorted(moved, key=self._matched_sort_key)),
            added=tuple(sorted(remaining_local.values(), key=self._local_sort_key)),
            deleted=(
                tuple(sorted(remaining_remote.values(), key=self._remote_sort_key))
                if snapshot_complete
                else ()
            ),
            rejected=tuple(
                sorted(enriched_rejected, key=lambda item: item.relative_path)
            ),
            ambiguous=tuple(ambiguous),
        )

    @staticmethod
    def _group_local_by_hash(
        files,
    ) -> dict[str, list[LocalFileSnapshot]]:
        grouped: dict[str, list[LocalFileSnapshot]] = defaultdict(list)
        for file in files:
            grouped[file.content_hash].append(file)
        return grouped

    @staticmethod
    def _group_remote_by_hash(
        files,
    ) -> dict[str, list[RemoteFileSnapshot]]:
        grouped: dict[str, list[RemoteFileSnapshot]] = defaultdict(list)
        for file in files:
            if ProjectFileSyncPlanner._is_healthy_remote(file):
                grouped[file.content_hash].append(file)
        return grouped

    @staticmethod
    def _is_healthy_remote(file: RemoteFileSnapshot) -> bool:
        """检测远程文件健康状态是否可访问"""
        return file.status == "active" and file.upload_status == "success"

    @staticmethod
    def _matched_sort_key(action: MatchedFileAction) -> str:
        return action.local_file.relative_path

    @staticmethod
    def _local_sort_key(file: LocalFileSnapshot) -> str:
        return file.relative_path

    @staticmethod
    def _remote_sort_key(file: RemoteFileSnapshot) -> str:
        return file.relative_path
