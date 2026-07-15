"""项目上下文文件哈希工具。"""
from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["content_hash", "quick_fingerprint"]

_DEFAULT_CHUNK_SIZE = 65536


def content_hash(
    path: str | Path,
    *,
    algo: str = "sha256",
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> str:
    """流式计算文件内容哈希，避免大文件一次性读入内存。"""
    hasher = hashlib.new(algo)
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def quick_fingerprint(path: str | Path, size: int, mtime: float) -> str:
    """用 path、size、mtime 构造增量扫描快速指纹。"""
    raw = f"{path}|{size}|{mtime}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()
