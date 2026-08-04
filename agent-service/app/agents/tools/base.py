"""Agent 工具公共抽象。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.agents.tools.schemas import ToolExecutionContext


class BaseAgentTool(ABC):
    """声明模型可见契约，并将执行委托给业务模块公开 Service。"""

    name: str = ""
    description: str = ""
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    operation: str = "read"
    requires_confirmation: bool = False
    timeout_seconds: float = 10.0

    def model_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }

    @abstractmethod
    async def execute(
        self,
        context: ToolExecutionContext,
        arguments: BaseModel,
    ) -> BaseModel:
        """调用业务 Service 并返回待校验的结构化结果。"""
