"""项目文件领域规则测试。"""
from __future__ import annotations

from hashlib import sha256

import pytest

from app.core.config import FileConfig
from app.core.errors import AppException, ErrorCode
from app.modules.project_file.domain import (
    normalize_relative_path,
    prepare_metadata,
    prepare_path_metadata,
)


def _config() -> FileConfig:
    return FileConfig(
        max_size_bytes=1024,
        ignored_directories=frozenset({".git", "node_modules"}),
        ignored_file_names=frozenset({".env"}),
        blocked_extensions=frozenset({"exe"}),
        blocked_mime_types=frozenset({"application/x-msdownload"}),
    )


def test_prepare_metadata_should_normalize_path_and_calculate_hashes() -> None:
    metadata = prepare_metadata(
        ".\\docs\\README.md",
        123,
        "项目说明".encode(),
        "text/markdown",
        _config(),
    )

    assert metadata.relative_path == "docs/README.md"
    assert metadata.content_hash == sha256("项目说明".encode()).hexdigest()
    assert metadata.path_hash == sha256(b"docs/README.md").hexdigest()
    assert metadata.extension == "md"


def test_prepare_path_metadata_should_not_fabricate_content_metadata() -> None:
    metadata = prepare_path_metadata(
        "src/main.py",
        456,
        _config(),
    )

    assert metadata.relative_path == "src/main.py"
    assert metadata.file_name == "main.py"
    assert not hasattr(metadata, "content_hash")


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("../secret.txt", ErrorCode.PARAM_INVALID),
        ("node_modules/pkg.js", ErrorCode.FILE_PATH_IGNORED),
        (".env", ErrorCode.FILE_PATH_IGNORED),
        ("bin/tool.exe", ErrorCode.FILE_EXTENSION_NOT_ALLOWED),
    ],
)
def test_invalid_path_should_return_frozen_error(path: str, error: ErrorCode) -> None:
    with pytest.raises(AppException) as caught:
        prepare_metadata(path, 0, b"content", None, _config())

    assert caught.value.error is error


def test_normalize_relative_path_should_reject_absolute_path() -> None:
    with pytest.raises(AppException):
        normalize_relative_path("/tmp/project.md")
