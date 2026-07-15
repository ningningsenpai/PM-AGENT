"""项目上下文文件树索引写入器。"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.project.context.schemas import FileNode, ScanResult, ScanSummary

__all__ = ["INDEX_FILE_NAME", "TreeIndexWriter"]

INDEX_FILE_NAME = "Project_Index.json"


class TreeIndexWriter:
    """TreeIndexWriter 负责读取和写入文件树扫描索引。"""

    @staticmethod
    def index_path(output_dir: str | Path) -> Path:
        """返回扫描索引文件路径。"""
        return Path(output_dir).resolve() / INDEX_FILE_NAME

    def exists(self, output_dir: str | Path) -> bool:
        """判断扫描索引是否存在。"""
        return self.index_path(output_dir).exists()

    def read(self, output_dir: str | Path) -> ScanResult | None:
        """读取扫描索引；不存在时返回 None。"""
        index_path = self.index_path(output_dir)
        if not index_path.exists():
            return None
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return self._from_dict(data)

    def write(self, result: ScanResult, output_dir: str | Path) -> Path:
        """写入扫描索引；调用方必须保证 output_dir 是受控目录。"""
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.index_path(target_dir)
        json_path.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return json_path

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ScanResult:
        summary_data = data.get("summary") or {}
        nodes_data = data.get("nodes") or []
        return ScanResult(
            root_path=str(data.get("root_path") or ""),
            generated_at=str(data.get("generated_at") or ""),
            nodes=[FileNode(**node) for node in nodes_data],
            summary=ScanSummary(**summary_data),
        )
