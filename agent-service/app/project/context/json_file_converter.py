"""JSON 内容与文件对象之间的转换工具。"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

__all__ = ["JsonFileConverter"]


class JsonFileConverter:
    """将 JSON 内容转换为内存文件或指定路径下的正式文件。"""

    def to_memory_file(self, content: Any) -> BytesIO:
        """生成位于内存中的二进制 JSON 文件对象。"""
        return BytesIO(self._serialize(content))

    def to_file(self, content: Any, target_path: str | Path) -> Path:
        """将 JSON 内容写入指定路径，并返回最终文件路径。"""
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self._serialize(content))
        return path

    @staticmethod
    def _serialize(content: Any) -> bytes:
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError as exception:
                raise ValueError("JSON 字符串格式无效") from exception

        try:
            text = json.dumps(content, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as exception:
            raise TypeError("内容包含无法序列化为 JSON 的对象") from exception
        return f"{text}\n".encode("utf-8")
