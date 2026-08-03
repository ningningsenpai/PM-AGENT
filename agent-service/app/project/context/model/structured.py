"""结构化项目上下文模型调用。"""
from __future__ import annotations

import asyncio
from typing import TypeVar

from pydantic import BaseModel

from app.project.context.model.client import ProjectContextModelClient

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredJsonGenerator:
    """统一执行 JSON 模型调用并用 Pydantic 校验结果。"""

    def __init__(self, client: ProjectContextModelClient | None = None) -> None:
        self._client = client or ProjectContextModelClient()

    async def generate(self, prompt: str, model_type: type[ModelT]) -> ModelT:
        response = await asyncio.to_thread(
            self._client.generate,
            prompt,
            response_format="json",
        )
        return model_type.model_validate_json(response.content)
