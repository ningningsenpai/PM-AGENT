"""项目文件领域状态与纯计算。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import mimetypes
from pathlib import PurePosixPath
import unicodedata

from app.core.config import FileConfig
from app.core.errors import AppException, ErrorCode


class FileBusinessType(StrEnum):
    PROJECT = "project"
    USER = "user"
    SYSTEM = "system"


class ProjectFileStatus(StrEnum):
    UPLOADING = "uploading"
    ACTIVE = "active"
    UPDATING = "updating"
    UPLOAD_FAILED = "upload_failed"
    VERIFY_REQUIRED = "verify_required"
    MISSING = "missing"
    DELETING = "deleting"
    DELETE_FAILED = "delete_failed"


class ProjectFileUploadStatus(StrEnum):
    NOT_UPLOADED = "not_uploaded"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FileMetadata:
    relative_path: str
    file_name: str
    extension: str | None
    path_hash: str
    content_type: str
    content: bytes
    size_bytes: int
    source_mtime_ms: int
    quick_fingerprint: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class FilePathMetadata:
    relative_path: str
    file_name: str
    extension: str | None
    path_hash: str
    source_mtime_ms: int


def prepare_metadata(
    relative_path: str,
    source_mtime_ms: int,
    content: bytes,
    supplied_content_type: str | None,
    config: FileConfig,
) -> FileMetadata:
    normalized_path = normalize_relative_path(relative_path)
    file_name = PurePosixPath(normalized_path).name
    extension = file_extension(file_name)
    validate_path(normalized_path, config)
    validate_extension(extension, config)
    if source_mtime_ms < 0:
        raise AppException(ErrorCode.PARAM_INVALID, "源文件修改时间不能小于0")
    if not content:
        raise AppException(ErrorCode.PARAM_INVALID, "上传文件不能为空")
    if len(content) > config.max_size_bytes:
        raise AppException(ErrorCode.FILE_TOO_LARGE)

    guessed_type = mimetypes.guess_type(file_name)[0]
    content_type = (supplied_content_type or guessed_type or "application/octet-stream").lower()
    if content_type in config.blocked_mime_types:
        raise AppException(ErrorCode.FILE_MIME_TYPE_BLOCKED)

    path_digest = sha256(normalized_path.encode("utf-8")).hexdigest()
    raw_quick = f"{normalized_path}\0{len(content)}\0{source_mtime_ms}".encode()
    return FileMetadata(
        relative_path=normalized_path,
        file_name=file_name,
        extension=extension,
        path_hash=path_digest,
        content_type=content_type,
        content=content,
        size_bytes=len(content),
        source_mtime_ms=source_mtime_ms,
        quick_fingerprint=sha256(raw_quick).hexdigest(),
        content_hash=sha256(content).hexdigest(),
    )


def prepare_path_metadata(
    relative_path: str,
    source_mtime_ms: int,
    config: FileConfig,
) -> FilePathMetadata:
    normalized_path = normalize_relative_path(relative_path)
    file_name = PurePosixPath(normalized_path).name
    extension = file_extension(file_name)
    validate_path(normalized_path, config)
    validate_extension(extension, config)
    if source_mtime_ms < 0:
        raise AppException(ErrorCode.PARAM_INVALID, "源文件修改时间不能小于0")
    return FilePathMetadata(
        relative_path=normalized_path,
        file_name=file_name,
        extension=extension,
        path_hash=sha256(normalized_path.encode("utf-8")).hexdigest(),
        source_mtime_ms=source_mtime_ms,
    )


def normalize_relative_path(relative_path: str) -> str:
    if relative_path is None:
        raise AppException(ErrorCode.PARAM_INVALID, "文件相对路径不能为空")
    normalized = unicodedata.normalize(
        "NFC",
        relative_path.strip().replace("\\", "/"),
    )
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    parts = path.parts
    if (
        not normalized
        or len(normalized) > 512
        or normalized.startswith("/")
        or (len(normalized) > 2 and normalized[1:3] == ":/")
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise AppException(ErrorCode.PARAM_INVALID, "文件相对路径不合法")
    return str(path)


def validate_path(relative_path: str, config: FileConfig) -> None:
    parts = PurePosixPath(relative_path).parts
    ignored_directories = {item.lower() for item in config.ignored_directories}
    for directory in parts[:-1]:
        if directory.lower() in ignored_directories:
            raise AppException(
                ErrorCode.FILE_PATH_IGNORED,
                f"文件路径命中忽略目录：{directory}",
            )
    file_name = parts[-1]
    if file_name.lower() in {item.lower() for item in config.ignored_file_names}:
        raise AppException(
            ErrorCode.FILE_PATH_IGNORED,
            f"文件名命中忽略规则：{file_name}",
        )
    if file_name.lower().startswith(".env."):
        raise AppException(
            ErrorCode.FILE_PATH_IGNORED,
            f"文件名命中忽略规则：{file_name}",
        )


def validate_extension(extension: str | None, config: FileConfig) -> None:
    normalized = (extension or "").lower()
    if normalized in config.blocked_extensions:
        display = f".{normalized}" if normalized else "无扩展名"
        raise AppException(
            ErrorCode.FILE_EXTENSION_NOT_ALLOWED,
            f"禁止上传该扩展名的文件：{display}",
        )


def file_extension(file_name: str) -> str | None:
    dot_index = file_name.rfind(".")
    if dot_index <= 0 or dot_index == len(file_name) - 1:
        return None
    return file_name[dot_index + 1 :].lower()
