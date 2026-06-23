# 忽略规则：判断目录或文件是否应跳过扫描 / 跳过 hash。
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["DEFAULT_SKIP_DIRS", "SKIP_HASH_SUFFIXES", "IgnoreDecision", "IgnoreRules"]

DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "target",
    "out",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".gradle",
    ".mvn",
    ".qdrant-data",
    "mysql-data",
})

SKIP_HASH_SUFFIXES: frozenset[str] = frozenset({
    ".env",
    ".pem",
    ".key",
    ".crt",
    ".p12",
    ".jks",
    ".sqlite",
    ".db",
    ".log",
    ".lock",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".mp4",
    ".mov",
    ".pdf",
})


@dataclass(frozen=True)
class IgnoreDecision:
    ignored: bool
    reason: str = ""


class IgnoreRules:
    """项目扫描忽略规则集合。"""

    def __init__(self, extra_skip_dirs: set[str] | None = None) -> None:
        self.skip_dirs = set(DEFAULT_SKIP_DIRS)
        if extra_skip_dirs:
            self.skip_dirs.update(extra_skip_dirs)

    def should_ignore_dir(self, path: Path) -> IgnoreDecision:
        if path.name in self.skip_dirs:
            return IgnoreDecision(True, f"skip_dir:{path.name}")
        return IgnoreDecision(False)

    def should_skip_hash(self, path: Path, size_bytes: int, max_hash_bytes: int) -> IgnoreDecision:
        suffix = path.suffix.lower()
        if suffix in SKIP_HASH_SUFFIXES:
            return IgnoreDecision(True, f"suffix:{suffix}")
        if path.name.startswith(".env"):
            return IgnoreDecision(True, "env_file")
        if size_bytes > max_hash_bytes:
            return IgnoreDecision(True, f"too_large:{size_bytes}")
        return IgnoreDecision(False)
