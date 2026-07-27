"""项目文件领域规则单元测试。"""

from __future__ import annotations

from hashlib import sha256

import pytest

from app.core.errors import AppException, ErrorCode
from app.modules.project_file.management.domain import (
    file_extension,
    normalize_relative_path,
    prepare_metadata,
    prepare_path_metadata,
)
from tests.unit.modules.project_file.management.factories import file_config


def test_prepare_metadata_builds_normalized_fingerprints() -> None:
    """验证文件元数据会规范化路径并计算稳定指纹。

    @Param relative_path: 使用反斜杠和当前目录前缀的相对路径。
    @Param source_mtime_ms: 非负源文件修改时间。
    @Param content: 非空文件字节内容。
    @Param supplied_content_type: 显式提供的合法 MIME 类型。
    @Param config: 文件校验配置。
    @Return: 路径、类型、大小和哈希均正确的 FileMetadata。
    """
    content = "项目说明".encode()

    metadata = prepare_metadata(
        ".\\docs\\README.md",
        123,
        content,
        "TEXT/MARKDOWN",
        file_config(),
    )

    assert metadata.relative_path == "docs/README.md"
    assert metadata.file_name == "README.md"
    assert metadata.extension == "md"
    assert metadata.content_type == "text/markdown"
    assert metadata.content_hash == sha256(content).hexdigest()
    assert metadata.path_hash == sha256(b"docs/README.md").hexdigest()


def test_prepare_path_metadata_excludes_content_fields() -> None:
    """验证路径修改只生成路径相关元数据。

    @Param relative_path: 合法的新相对路径。
    @Param source_mtime_ms: 非负源文件修改时间。
    @Param config: 文件校验配置。
    @Return: 不包含内容哈希的 FilePathMetadata。
    """
    metadata = prepare_path_metadata("src/main.py", 456, file_config())

    assert metadata.relative_path == "src/main.py"
    assert metadata.file_name == "main.py"
    assert metadata.extension == "py"
    assert not hasattr(metadata, "content_hash")


@pytest.mark.parametrize(
    ("relative_path", "expected_error"),
    [
        ("", ErrorCode.PARAM_INVALID),
        ("/tmp/readme.md", ErrorCode.PARAM_INVALID),
        ("../secret.txt", ErrorCode.PARAM_INVALID),
        ("node_modules/pkg.js", ErrorCode.FILE_PATH_IGNORED),
        (".env", ErrorCode.FILE_PATH_IGNORED),
        (".env.local", ErrorCode.FILE_PATH_IGNORED),
        ("bin/tool.exe", ErrorCode.FILE_EXTENSION_NOT_ALLOWED),
    ],
)
def test_prepare_metadata_rejects_invalid_path(
    relative_path: str,
    expected_error: ErrorCode,
) -> None:
    """验证非法路径和被忽略文件会返回冻结错误码。

    @Param relative_path: 参数化的非法或被忽略路径。
    @Param source_mtime_ms: 固定的非负修改时间。
    @Param content: 固定的非空文件内容。
    @Param supplied_content_type: 未显式提供 MIME 类型。
    @Param config: 包含忽略和禁用规则的文件配置。
    @Return: 抛出 expected_error 对应的 AppException。
    """
    with pytest.raises(AppException) as caught:
        prepare_metadata(
            relative_path,
            0,
            b"content",
            None,
            file_config(),
        )

    assert caught.value.error is expected_error


@pytest.mark.parametrize(
    ("source_mtime_ms", "content", "content_type", "expected_error"),
    [
        (-1, b"content", "text/plain", ErrorCode.PARAM_INVALID),
        (0, b"", "text/plain", ErrorCode.PARAM_INVALID),
        (0, b"x" * 1025, "text/plain", ErrorCode.FILE_TOO_LARGE),
        (
            0,
            b"content",
            "application/x-msdownload",
            ErrorCode.FILE_MIME_TYPE_BLOCKED,
        ),
    ],
)
def test_prepare_metadata_rejects_invalid_content(
    source_mtime_ms: int,
    content: bytes,
    content_type: str,
    expected_error: ErrorCode,
) -> None:
    """验证非法时间、内容、大小或 MIME 类型会被拒绝。

    @Param relative_path: 固定的合法相对路径。
    @Param source_mtime_ms: 参数化的源文件修改时间。
    @Param content: 参数化的文件内容。
    @Param supplied_content_type: 参数化的 MIME 类型。
    @Param config: 包含大小和 MIME 规则的文件配置。
    @Return: 抛出 expected_error 对应的 AppException。
    """
    with pytest.raises(AppException) as caught:
        prepare_metadata(
            "docs/README.md",
            source_mtime_ms,
            content,
            content_type,
            file_config(),
        )

    assert caught.value.error is expected_error


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("README.md", "md"),
        ("archive.TAR.GZ", "gz"),
        (".env", None),
        ("README", None),
        ("README.", None),
    ],
)
def test_file_extension_handles_edge_cases(
    file_name: str,
    expected: str | None,
) -> None:
    """验证扩展名解析覆盖隐藏文件和无扩展名场景。

    @Param file_name: 参数化的文件名。
    @Return: 小写扩展名或 None。
    """
    assert file_extension(file_name) == expected


def test_normalize_relative_path_normalizes_unicode_and_separators() -> None:
    """验证路径规范化统一 Unicode 和目录分隔符。

    @Param relative_path: 包含分解字符和反斜杠的相对路径。
    @Return: 使用 NFC 字符和正斜杠的相对路径。
    """
    normalized = normalize_relative_path("docs\\Cafe\u0301.md")

    assert normalized == "docs/Café.md"
