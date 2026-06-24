"""项目上下文扫描数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["FileNode", "ProjectInitRequest", "ScanResult", "ScanSummary"]


@dataclass
class FileNode:
    """文件树节点：记录目录或文件的扫描结果。"""

    path: str
    name: str
    size_bytes: int
    mtime: float
    depth: int
    is_dir: bool
    scan_status: str = "active"
    ignore_reason: str = ""
    quick_fingerprint: str = ""
    content_hash: str = ""


@dataclass
class ScanSummary:
    """扫描统计摘要。"""

    total_files: int = 0
    hashed_files: int = 0
    ignored_dirs: int = 0
    skipped_files: int = 0
    total_nodes: int = 0


@dataclass
class ScanResult:
    """项目文件树扫描结果。"""

    root_path: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    nodes: list[FileNode] = field(default_factory=list)
    summary: ScanSummary = field(default_factory=ScanSummary)


@dataclass
class ProjectInitRequest:
    """项目初始化请求。"""

    project_id: int
    project_name: str
    root_path: str
    output_dir: str
