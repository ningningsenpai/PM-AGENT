# 扫描结果写入器：当前阶段将结果写入 tests 目录，后续可切换到系统私有目录。
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.project_context.schemas import FileNode, ScanResult, ScanSummary

__all__ = ["INDEX_FILE_NAME", "TreeIndexWriter"]

INDEX_FILE_NAME = "Project_Index.json"


class TreeIndexWriter:
    """负责读取和写入文件树扫描索引。"""

    def index_path(self, output_dir: str | Path) -> Path:
        return Path(output_dir).resolve() / INDEX_FILE_NAME

    def exists(self, output_dir: str | Path) -> bool:
        return self.index_path(output_dir).exists()

    def read(self, output_dir: str | Path) -> ScanResult | None:
        index_path = self.index_path(output_dir)
        if not index_path.exists():
            return None
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return self._from_dict(data)

    def write(self, result: ScanResult, output_dir: str | Path) -> Path:
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.index_path(target_dir)
        json_path.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return json_path

    def _from_dict(self, data: dict[str, Any]) -> ScanResult:
        summary_data = data.get("summary") or {}
        nodes_data = data.get("nodes") or []
        return ScanResult(
            root_path=str(data.get("root_path") or ""),
            generated_at=str(data.get("generated_at") or ""),
            nodes=[FileNode(**node) for node in nodes_data],
            summary=ScanSummary(**summary_data),
        )
