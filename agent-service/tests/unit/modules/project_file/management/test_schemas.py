"""项目文件请求模型单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.project_file.management.schemas import UpdateProjectFilePathRequest


def test_update_path_request_accepts_valid_fields() -> None:
    """验证文件路径修改请求接受合法字段。

    @Param relative_path: 长度合法的相对路径。
    @Param source_mtime_ms: 非负源文件修改时间。
    @Param lock_version: 非负乐观锁版本。
    @Return: 字段保持一致的 UpdateProjectFilePathRequest。
    """
    request = UpdateProjectFilePathRequest(
        relative_path="docs/README.md",
        source_mtime_ms=100,
        lock_version=2,
    )

    assert request.relative_path == "docs/README.md"
    assert request.source_mtime_ms == 100
    assert request.lock_version == 2


@pytest.mark.parametrize(
    ("relative_path", "source_mtime_ms", "lock_version"),
    [
        ("", 0, 0),
        ("docs/README.md", -1, 0),
        ("docs/README.md", 0, -1),
    ],
)
def test_update_path_request_rejects_invalid_fields(
    relative_path: str,
    source_mtime_ms: int,
    lock_version: int,
) -> None:
    """验证文件路径修改请求拒绝空路径或负数状态字段。

    @Param relative_path: 参数化的相对路径。
    @Param source_mtime_ms: 参数化的源文件修改时间。
    @Param lock_version: 参数化的乐观锁版本。
    @Return: 抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        UpdateProjectFilePathRequest(
            relative_path=relative_path,
            source_mtime_ms=source_mtime_ms,
            lock_version=lock_version,
        )
