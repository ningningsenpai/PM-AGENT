"""项目上下文扫描服务。"""
from __future__ import annotations

from pathlib import Path

from app.project.context.indexer.tree_index import TreeIndexWriter
from app.project.context.scanner.walker import walk
from app.project.context.schemas import FileNode, ScanResult

__all__ = ["ProjectContextScanService"]


class ProjectContextScanService:
    """ProjectContextScanService 编排文件树扫描、更新检测和索引写入。"""

    def __init__(self, writer: TreeIndexWriter | None = None) -> None:
        self.writer = writer or TreeIndexWriter()

    def scan(self, root_path: str | Path) -> ScanResult:
        """扫描项目根目录并返回文件树。"""
        return walk(root_path)

    def scan_to_directory(self, root_path: str | Path, output_dir: str | Path) -> tuple[ScanResult, Path]:
        """扫描项目根目录并把结果写入受控输出目录。"""
        result = self.scan(root_path)
        json_path = self.writer.write(result, output_dir)
        return result, json_path

    def check_update_and_write(self, input_dir: str | Path, output_dir: str | Path) -> tuple[bool, Path]:
        """扫描根目录，若文件树内容变化则覆盖旧索引。"""
        current = self.scan(input_dir)
        previous = self.writer.read(output_dir)
        index_path = self.writer.index_path(output_dir)
        changed = previous is None or self._has_changed(previous, current)
        if changed:
            index_path = self.writer.write(current, output_dir)
        return changed, index_path

    def _has_changed(self, previous: ScanResult, current: ScanResult) -> bool:
        return self._node_fingerprint_map(previous) != self._node_fingerprint_map(current)

    def _node_fingerprint_map(self, result: ScanResult) -> dict[str, tuple]:
        fingerprint_map = {}
        for node in result.nodes:
            fingerprint_map[node.path] = self._node_fingerprint(node)
        return fingerprint_map

    def _node_fingerprint(self, node: FileNode) -> tuple:
        return (
            node.is_dir,
            node.scan_status,
            node.ignore_reason,
            node.size_bytes,
            node.quick_fingerprint,
            node.content_hash,
        )
