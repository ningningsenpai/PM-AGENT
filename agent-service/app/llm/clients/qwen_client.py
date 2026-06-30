"""Qwen 模型适配器。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import BaseLLMClient
from app.llm.registry import register_llm
from app.streaming.metrics import LLMChatResult, LLMStreamChunk, LLMTokenUsage


@register_llm("qwen")
class QwenClient(BaseLLMClient):
    """Qwen 模型适配器；当前最小实现支持 Ollama generate 接口。"""

    async def chat_with_usage(self, messages: list[dict]) -> LLMChatResult:
        prompt = self._messages_to_prompt(messages)
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.config.context_window_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds()) as client:
            response = await client.post(f"{self.config.base_url.rstrip('/')}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return LLMChatResult(
            content=str(data.get("response") or ""),
            usage=LLMTokenUsage(
                provider=self.provider,
                model=str(data.get("model") or self.config.model),
                input_tokens=int(data.get("prompt_eval_count") or 0),
                output_tokens=int(data.get("eval_count") or 0),
            ),
        )

    async def stream_chat_with_usage(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        result = await self.chat_with_usage(messages)
        if result.content:
            yield LLMStreamChunk(content=result.content)
        if result.usage:
            yield LLMStreamChunk(usage=result.usage)

    @staticmethod
    def _messages_to_prompt(messages: list[dict]) -> str:
        parts = []
        for message in messages:
            role = message.get("role") or "user"
            content = message.get("content") or ""
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def _timeout_seconds(self) -> float:
        timeout = self.config.extra.get("timeout_seconds")
        try:
            return float(timeout)
        except (TypeError, ValueError):
            return 120.0
