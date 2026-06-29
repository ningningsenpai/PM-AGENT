"""项目上下文文件树遍历。"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.project.context.schemas import FileNode, ScanResult, ScanSummary
from app.project.context.scanner.hashing import content_hash, quick_fingerprint
from app.project.context.scanner.ignore_rules import IgnoreRules

__all__ = ["DEFAULT_MAX_HASH_BYTES", "walk"]

DEFAULT_MAX_HASH_BYTES = 10 * 1024 * 1024


def walk(
    root_path: str | Path,
    *,
    max_hash_bytes: int = DEFAULT_MAX_HASH_BYTES,
    extra_skip_dirs: Iterable[str] | None = None,
) -> ScanResult:
    """从根目录向下遍历，生成正式的文件树扫描结果。"""
    root = Path(root_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"root_path 不存在或不是目录: {root}")

    ignore_rules = IgnoreRules(set(extra_skip_dirs or []))
    nodes: list[FileNode] = []
    summary = ScanSummary()

    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current_dir, depth = stack.pop()
        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (PermissionError, OSError) as exc:
            nodes.append(_build_error_dir_node(current_dir, root, depth, exc))
            continue

        for entry in entries:
            rel_path = str(entry.relative_to(root)).replace("\\", "/")
            if entry.is_dir():
                _handle_dir_entry(entry, rel_path, depth, stack, nodes, summary, ignore_rules)
                continue
            nodes.append(_build_file_node(entry, rel_path, depth + 1, ignore_rules, max_hash_bytes, summary))

    nodes.sort(key=lambda node: node.path)
    summary.total_nodes = len(nodes)
    return ScanResult(root_path=str(root), nodes=nodes, summary=summary)


def _handle_dir_entry(
    entry: Path,
    rel_path: str,
    depth: int,
    stack: list[tuple[Path, int]],
    nodes: list[FileNode],
    summary: ScanSummary,
    ignore_rules: IgnoreRules,
) -> None:
    decision = ignore_rules.should_ignore_dir(entry)
    if decision.ignored:
        nodes.append(FileNode(
            path=rel_path,
            name=entry.name,
            size_bytes=0,
            mtime=_safe_mtime(entry),
            depth=depth + 1,
            is_dir=True,
            scan_status="ignored",
            ignore_reason=decision.reason,
        ))
        summary.ignored_dirs += 1
        return

    nodes.append(FileNode(
        path=rel_path,
        name=entry.name,
        size_bytes=0,
        mtime=_safe_mtime(entry),
        depth=depth + 1,
        is_dir=True,
    ))
    stack.append((entry, depth + 1))


def _build_file_node(
    entry: Path,
    rel_path: str,
    depth: int,
    ignore_rules: IgnoreRules,
    max_hash_bytes: int,
    summary: ScanSummary,
) -> FileNode:
    try:
        stat = entry.stat()
    except (PermissionError, OSError) as exc:
        return FileNode(
            path=rel_path,
            name=entry.name,
            size_bytes=0,
            mtime=0.0,
            depth=depth,
            is_dir=False,
            scan_status="error",
            ignore_reason=f"stat_failed:{exc}",
        )

    node = FileNode(
        path=rel_path,
        name=entry.name,
        size_bytes=stat.st_size,
        mtime=stat.st_mtime,
        depth=depth,
        is_dir=False,
        quick_fingerprint=quick_fingerprint(rel_path, stat.st_size, stat.st_mtime),
    )
    summary.total_files += 1

    decision = ignore_rules.should_skip_hash(entry, stat.st_size, max_hash_bytes)
    if decision.ignored:
        node.scan_status = "skipped_hash"
        node.ignore_reason = decision.reason
        summary.skipped_files += 1
        return node

    try:
        node.content_hash = content_hash(entry)
        summary.hashed_files += 1
    except (PermissionError, OSError) as exc:
        node.scan_status = "error"
        node.ignore_reason = f"hash_failed:{exc}"

    return node


def _build_error_dir_node(current_dir: Path, root: Path, depth: int, exc: OSError) -> FileNode:
    return FileNode(
        path=str(current_dir.relative_to(root)) if current_dir != root else ".",
        name=current_dir.name,
        size_bytes=0,
        mtime=0.0,
        depth=depth,
        is_dir=True,
        scan_status="error",
        ignore_reason=f"list_failed:{exc}",
    )


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
