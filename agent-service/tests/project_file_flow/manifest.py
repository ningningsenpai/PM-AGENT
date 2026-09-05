"""模拟前端收集项目目录文件，生成同步清单。"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import unicodedata
from pathlib import Path

# 与前端 file-upload.ts 的筛选规则保持一致，拒绝项只收集元数据。
MAX_FILE_SIZE = 50 * 1024 * 1024
IGNORED_DIRECTORIES = {
    ".git",
    ".gradle",
    ".idea",
    ".mvn",
    ".mypy_cache",
    ".pytest_cache",
    ".qdrant-data",
    ".svn",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "module",
    "mysql-data",
    "node_modules",
    "out",
    "target",
    "test",
    "tests",
    "venv",
}
IGNORED_FILES = {".ds_store", "desktop.ini", "thumbs.db"}
BLOCKED_EXTENSIONS = {
    "7z",
    "a",
    "apk",
    "appimage",
    "avi",
    "bin",
    "bmp",
    "bz2",
    "class",
    "dll",
    "dmg",
    "dylib",
    "ear",
    "exe",
    "flac",
    "gif",
    "gz",
    "ico",
    "iso",
    "jar",
    "jpeg",
    "jpg",
    "key",
    "lib",
    "map",
    "mkv",
    "mov",
    "mp3",
    "mp4",
    "msi",
    "o",
    "obj",
    "ogg",
    "pem",
    "png",
    "pyc",
    "pyo",
    "rar",
    "so",
    "tar",
    "tiff",
    "war",
    "wav",
    "webm",
    "webp",
    "xz",
    "zip",
}
BLOCKED_MIME_TYPES = {
    "application/java-archive",
    "application/vnd.android.package-archive",
    "application/x-7z-compressed",
    "application/x-apple-diskimage",
    "application/x-dosexec",
    "application/x-executable",
    "application/x-msdownload",
    "application/x-rar-compressed",
    "application/x-tar",
    "application/zip",
}


def rejection_reason(relative_path: str, size: int, content_type: str) -> str:
    path = Path(relative_path)
    for part in path.parts[:-1]:
        if part.lower() in IGNORED_DIRECTORIES:
            return f"命中忽略目录：{part}"
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return "本地环境变量文件"
    if name in IGNORED_FILES:
        return "系统或 IDE 临时文件"
    if size == 0:
        return "空文件"
    if size > MAX_FILE_SIZE:
        return "单文件超过 50MB"
    if path.suffix.lower().lstrip(".") in BLOCKED_EXTENSIONS:
        return f"不支持的文件后缀：{path.suffix}"
    if content_type in BLOCKED_MIME_TYPES or content_type.startswith(
        ("audio/", "image/", "video/")
    ):
        return f"不支持的文件类型：{content_type}"
    return ""


def build_manifest(source_dir: Path) -> dict:
    """保留源文件到规范化路径的映射，供下一阶段上传原始字节。"""
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise ValueError(f"测试文件夹不存在：{source_dir}")
    items, rejections, files = [], [], {}
    seen_paths: set[str] = set()

    def scan_error(error: OSError) -> None:
        raise ValueError(f"无法完整扫描目录：{error.filename}") from error

    for directory, directories, names in os.walk(source_dir, onerror=scan_error):
        directories.sort()
        for name in sorted(names):
            path = Path(directory) / name
            relative_path = unicodedata.normalize(
                "NFC", path.relative_to(source_dir).as_posix()
            )
            if not path.resolve().is_relative_to(source_dir):
                rejections.append(
                    {"relativePath": relative_path, "reason": "文件指向测试目录外"}
                )
                continue
            stat = path.stat()
            # 项目源码中的 TypeScript 不能按系统 MIME 映射识别成视频流。
            content_type = (
                "text/plain"
                if path.suffix.lower() in {".ts", ".tsx"}
                else mimetypes.guess_type(name)[0] or "application/octet-stream"
            )
            item = {
                "relativePath": relative_path,
                "sizeBytes": stat.st_size,
                "sourceMtimeMs": stat.st_mtime_ns // 1_000_000,
                "contentHash": None,
                "contentType": content_type,
            }
            reason = rejection_reason(relative_path, stat.st_size, content_type)
            if relative_path in seen_paths:
                rejections.append(
                    {"relativePath": relative_path, "reason": "相对路径重复"}
                )
                continue
            seen_paths.add(relative_path)
            if reason:
                rejections.append({"relativePath": relative_path, "reason": reason})
            else:
                with path.open("rb") as stream:
                    item["contentHash"] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
                files[relative_path] = {**item, "localPath": str(path)}
            items.append(item)
    return {
        "request": {"snapshotComplete": True, "scope": "project", "items": items},
        "files": files,
        "localRejections": rejections,
    }
