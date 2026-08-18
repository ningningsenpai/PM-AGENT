"""请求级 Agent 工具注册表。"""
from __future__ import annotations

import re
from collections.abc import Iterable

from app.agents.tools.base import BaseAgentTool

_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ToolRegistry:
    """显式注册当前请求可用工具并生成模型函数定义。"""

    def __init__(self, tools: Iterable[BaseAgentTool] = ()) -> None:
        self._tools: dict[str, BaseAgentTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: BaseAgentTool) -> None:
        """注册工具并校验名称。"""
        if not _TOOL_NAME_PATTERN.fullmatch(tool.name):
            raise ValueError(f"工具名称不合法：{tool.name!r}")
        if not tool.description.strip():
            raise ValueError(f"工具 {tool.name!r} 缺少用途描述")
        if tool.name in self._tools:
            raise ValueError(f"工具名称重复：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseAgentTool | None:
        return self._tools.get(name)

    def definitions(self) -> list[dict]:
        return [self._tools[name].model_definition() for name in sorted(self._tools)]

    def __len__(self) -> int:
        return len(self._tools)
