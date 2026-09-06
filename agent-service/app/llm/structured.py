"""结构化项目上下文模型调用。"""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import BaseLLMClient

ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


class StructuredOutputError(ValueError):
    """可向业务层回传的输出错误，消息不包含模型正文或校验输入值。"""


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
        logger.info(
            "结构化模型生成完成 schema=%s maxTokens=%s finishReason=%s "
            "contentChars=%s reasoningChars=%s outputTokens=%s",
            model_type.__name__,
            self._max_tokens,
            turn.finish_reason,
            len(turn.content),
            len(turn.reasoning_content or ""),
            turn.usage.output_tokens if turn.usage else None,
        )
        if turn.finish_reason == "length":
            raise StructuredOutputError(
                f"模型结构化输出达到 token 上限（max_tokens={self._max_tokens}），结果不完整"
            )
        if not turn.content.strip():
            raise StructuredOutputError("模型未返回结构化 JSON 内容")
        try:
            return model_type.model_validate_json(turn.content)
        except ValidationError as exception:
            errors = [
                {"loc": str(error["loc"])[:200], "type": error["type"]}
                for error in exception.errors(
                    include_input=False, include_context=False, include_url=False
                )[:20]
            ]
            logger.warning(
                "结构化模型输出校验失败 schema=%s errorCount=%s errors=%s",
                model_type.__name__,
                exception.error_count(),
                json.dumps(errors, ensure_ascii=False),
            )
            raise StructuredOutputError(
                "模型返回的 JSON 不符合字段要求，请查看结构化输出校验日志"
            ) from None
