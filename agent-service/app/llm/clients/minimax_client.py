"""MiniMax 模型适配器。

MiniMax 的 Chat Completion 协议与 OpenAI 兼容性不完全：
- 鉴权同为 ``Authorization: Bearer <api_key>``；
- 部分接口需要在 query 或 body 中携带 ``GroupId``；
- 流式分隔符与字段命名存在差异；
- 工具调用字段命名也与 OpenAI 不同。

为避免污染公共基类，此处独立实现 ``BaseLLMClient``。
当前版本作为占位骨架，请求体结构按 OpenAI 风格临时填充，
正式接入时按官方文档调整。
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.llm.base import BaseLLMClient
from app.llm.registry import register_llm
from app.streaming.metrics import LLMChatResult, LLMStreamChunk


@register_llm("minimax")
class MiniMaxClient(BaseLLMClient):
    """MiniMax 模型适配器（占位实现，正式接入前需对照官方文档调整）。"""

    default_temperature: float = 0.2

    def _endpoint(self) -> str:
        """MiniMax 的 chatcompletion 路径与 group_id 拼接。

        TODO 正式接入时确认路径：当前占位为 ``/text/chatcompletion_v2``。
        """
        base = self.config.base_url.rstrip("/")
        url = f"{base}/text/chatcompletion_v2"
        group_id = self.config.extra.get("group_id", "")
        if group_id:
            url = f"{url}?GroupId={group_id}"
        return url

    def _headers(self) -> dict[str, str]:
        self.config.require_api_key(self.provider)
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, messages: list[dict], stream: bool) -> dict:
        # TODO 对齐 MiniMax 字段命名（如 ``tokens_to_generate``、``reply_constraints``）。
        return {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.default_temperature,
            "stream": stream,
        }

    async def chat_with_usage(self, messages: list[dict]) -> LLMChatResult:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._endpoint(),
                headers=self._headers(),
                json=self._build_body(messages, stream=False),
            )
            response.raise_for_status()
            data = response.json()
            # TODO MiniMax 的响应字段命名以官方文档为准，当前按 OpenAI 风格占位。
            return LLMChatResult(content=data["choices"][0]["message"]["content"])

    async def stream_chat_with_usage(
        self,
        messages: list[dict],
    ) -> AsyncIterator[LLMStreamChunk]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                self._endpoint(),
                headers=self._headers(),
                json=self._build_body(messages, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line.removeprefix("data: ").strip()
                    if payload == "[DONE]":
                        break
                    data = json.loads(payload)
                    # TODO MiniMax 增量字段路径需对照官方文档调整。
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield LLMStreamChunk(content=content)
