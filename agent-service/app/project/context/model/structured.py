"""结构化项目上下文模型调用。"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import BaseLLMClient

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredJsonGenerator:
    """统一执行 JSON 模型调用并用 Pydantic 校验结果。"""

    def __init__(
        self,
        client: BaseLLMClient,
        *,
        max_tokens: int,
        timeout_seconds: float,
    ) -> None:
        self._client = client
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds

    async def generate(self, prompt: str, model_type: type[ModelT]) -> ModelT:
        turn = await self._client.complete_turn(
            [
                {
                    "role": "system",
                    "content": "你必须只返回一个合法的 JSON 对象，不得输出 Markdown 或解释文字。",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=self._max_tokens,
            temperature=0,
            timeout_seconds=self._timeout_seconds,
        )
        if turn.finish_reason == "length":
            raise ValueError("模型结构化输出达到 token 上限，结果不完整")
        if not turn.content.strip():
            raise ValueError("模型未返回结构化 JSON 内容")
        return model_type.model_validate_json(turn.content)
