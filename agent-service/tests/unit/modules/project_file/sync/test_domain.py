"""项目文件同步差异领域测试。"""

from __future__ import annotations

from hashlib import sha256

import pytest

from app.core.errors import AppException, ErrorCode
from app.modules.project_file.sync.domain import (
    LocalFileSnapshot,
    ProjectFileSyncPlanner,
    RejectedFileSnapshot,
    RemoteFileSnapshot,
    prepare_local_snapshot,
)
from tests.unit.modules.project_file.management.factories import file_config


def _hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _local(path: str, content: str) -> LocalFileSnapshot:
    return LocalFileSnapshot(path, 10, 100, _hash(content), "text/plain")


def _remote(file_id: int, path: str, content: str) -> RemoteFileSnapshot:
    return RemoteFileSnapshot(
        file_id=file_id,
        relative_path=path,
        size_bytes=10,
        source_mtime_ms=100,
        content_hash=_hash(content),
        content_type="text/plain",
        lock_version=file_id,
        status="active",
        upload_status="success",
    )


def test_prepare_local_snapshot_normalizes_and_validates_metadata() -> None:
    snapshot = prepare_local_snapshot(
        ".\\docs\\README.md",
        10,
        100,
        _hash("README").upper(),
        "TEXT/MARKDOWN",
        file_config(),
    )

    assert snapshot.relative_path == "docs/README.md"
    assert snapshot.content_hash == _hash("README")
    assert snapshot.content_type == "text/markdown"


@pytest.mark.parametrize(
    ("path", "size", "mtime", "content_hash", "content_type", "error"),
    [
        (".env", 10, 0, _hash("x"), "text/plain", ErrorCode.FILE_PATH_IGNORED),
        ("tool.exe", 10, 0, _hash("x"), None, ErrorCode.FILE_EXTENSION_NOT_ALLOWED),
        ("a.txt", 0, 0, _hash("x"), None, ErrorCode.PARAM_INVALID),
        ("a.txt", 1025, 0, _hash("x"), None, ErrorCode.FILE_TOO_LARGE),
        ("a.txt", 10, -1, _hash("x"), None, ErrorCode.PARAM_INVALID),
        ("a.txt", 10, 0, None, None, ErrorCode.PARAM_INVALID),
        ("a.txt", 10, 0, "bad-hash", None, ErrorCode.PARAM_INVALID),
        (
            "a.txt",
            10,
            0,
            _hash("x"),
            "application/x-msdownload",
            ErrorCode.FILE_MIME_TYPE_BLOCKED,
        ),
    ],
)
def test_prepare_local_snapshot_rejects_invalid_metadata(
    path: str,
    size: int,
    mtime: int,
    content_hash: str | None,
    content_type: str | None,
    error: ErrorCode,
) -> None:
    with pytest.raises(AppException) as caught:
        prepare_local_snapshot(
            path,
            size,
            mtime,
            content_hash,
            content_type,
            file_config(),
        )

    assert caught.value.error is error


def test_planner_classifies_all_sync_actions() -> None:
    duplicate_hash = _hash("duplicate")
    local_files = [
        _local("same.txt", "same"),
        _local("changed.txt", "new"),
        _local("new-location.txt", "moved"),
        _local("added.txt", "added"),
        LocalFileSnapshot("copy-a.txt", 10, 100, duplicate_hash, "text/plain"),
        LocalFileSnapshot("copy-b.txt", 10, 100, duplicate_hash, "text/plain"),
    ]
    remote_files = [
        _remote(1, "same.txt", "same"),
        _remote(2, "changed.txt", "old"),
        _remote(3, "old-location.txt", "moved"),
        _remote(4, "deleted.txt", "deleted"),
        RemoteFileSnapshot(
            5,
            "old-copy.txt",
            10,
            100,
            duplicate_hash,
            "text/plain",
            5,
            "active",
            "success",
        ),
        _remote(6, ".env", "secret"),
    ]
    rejected_files = [
        RejectedFileSnapshot(".env", "FILE_PATH_IGNORED", "文件路径不允许上传")
    ]

    plan = ProjectFileSyncPlanner().plan(
        local_files,
        remote_files,
        rejected_files,
        snapshot_complete=True,
    )

    assert [item.local_file.relative_path for item in plan.unchanged] == ["same.txt"]
    assert [item.local_file.relative_path for item in plan.modified] == ["changed.txt"]
    assert [item.local_file.relative_path for item in plan.moved] == [
        "new-location.txt"
    ]
    assert [item.remote_file.relative_path for item in plan.moved] == [
        "old-location.txt"
    ]
    assert [item.relative_path for item in plan.added] == ["added.txt"]
    assert [item.relative_path for item in plan.deleted] == ["deleted.txt"]
    assert plan.rejected[0].remote_file.file_id == 6
    assert len(plan.ambiguous) == 1
    assert [item.relative_path for item in plan.ambiguous[0].local_files] == [
        "copy-a.txt",
        "copy-b.txt",
    ]
    assert [item.file_id for item in plan.ambiguous[0].remote_files] == [5]


def test_planner_does_not_delete_for_partial_snapshot() -> None:
    plan = ProjectFileSyncPlanner().plan(
        [],
        [_remote(1, "remote.txt", "remote")],
        [],
        snapshot_complete=False,
    )

    assert plan.deleted == ()


def test_planner_treats_unhealthy_same_path_as_modified() -> None:
    remote = _remote(1, "same.txt", "same")
    remote = RemoteFileSnapshot(
        file_id=remote.file_id,
        relative_path=remote.relative_path,
        size_bytes=remote.size_bytes,
        source_mtime_ms=remote.source_mtime_ms,
        content_hash=remote.content_hash,
        content_type=remote.content_type,
        lock_version=remote.lock_version,
        status="upload_failed",
        upload_status="failed",
    )

    plan = ProjectFileSyncPlanner().plan(
        [_local("same.txt", "same")],
        [remote],
        [],
        snapshot_complete=True,
    )

    assert len(plan.modified) == 1
    assert plan.unchanged == ()


def test_planner_excludes_unhealthy_remote_from_move_matching() -> None:
    remote = _remote(1, "old.txt", "same")
    remote = RemoteFileSnapshot(
        file_id=remote.file_id,
        relative_path=remote.relative_path,
        size_bytes=remote.size_bytes,
        source_mtime_ms=remote.source_mtime_ms,
        content_hash=remote.content_hash,
        content_type=remote.content_type,
        lock_version=remote.lock_version,
        status="verify_required",
        upload_status="retrying",
    )

    plan = ProjectFileSyncPlanner().plan(
        [_local("new.txt", "same")],
        [remote],
        [],
        snapshot_complete=True,
    )

    assert plan.moved == ()
    assert [item.relative_path for item in plan.added] == ["new.txt"]
    assert [item.relative_path for item in plan.deleted] == ["old.txt"]
