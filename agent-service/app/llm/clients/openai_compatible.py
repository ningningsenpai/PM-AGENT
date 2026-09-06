"""OpenAI 兼容协议的通用客户端基类。

DeepSeek 与豆包（火山方舟）均采用与 OpenAI Chat Completions 高度兼容的
HTTP 协议，区别主要在于：
- 鉴权头形式（普遍是 ``Authorization: Bearer <api_key>``）；
- 域名与路径前缀；
- 默认模型名 / endpoint ID；
- 个别字段的可用性。

把公共的请求体构造、HTTP 调用、SSE 流式解析放在这里，子类只需声明
``provider`` 名即可被工厂识别。
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.llm.base import BaseLLMClient
from app.llm.contracts import (
    LLMAssistantTurn,
    LLMToolCall,
    LLMToolCallDelta,
    LLMTurnStreamEvent,
)
from app.streaming.metrics import LLMChatResult, LLMStreamChunk, LLMTokenUsage

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI Chat Completions 兼容客户端的公共实现。"""

    # 默认温度，可由子类或后续配置覆盖。
    default_temperature: float = 0.2
    # 当前只让 DeepSeek 开启真实 usage 解析，其他兼容厂商暂不统计。
    supports_real_usage: bool = False

    @property
    def max_output_tokens(self) -> int | None:
        return None

    def _endpoint(self) -> str:
        """拼接 chat/completions 接口的完整 URL。"""
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        """构造鉴权请求头；子类可重写以适配非 Bearer 的鉴权方式。"""
        self.config.require_api_key(self.provider)
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _build_body(
        self,
        messages: list[dict],
        stream: bool,
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """构造请求体；保留为单独方法方便子类追加厂商私有字段。"""
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": (
                self.default_temperature if temperature is None else temperature
            ),
            "stream": stream,
        }
        if stream and self.supports_real_usage:
            body["stream_options"] = {"include_usage": True}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        if response_format is not None:
            body["response_format"] = response_format
        if max_tokens is not None:
            if type(max_tokens) is not int or max_tokens <= 0:
                raise RuntimeError("模型请求的 max_tokens 必须为正整数")
            limit = self.max_output_tokens
            if limit is not None and max_tokens > limit:
                raise RuntimeError(
                    f"模型 {self.provider}/{self.config.model} 的 max_tokens={max_tokens} "
                    f"超过输出上限 {limit}，请检查输出 token 配置与调用参数"
                )
            body["max_tokens"] = max_tokens
        return body

    def _raise_for_status(
        self, response: httpx.Response, *, max_tokens: int | None = None
    ) -> None:
        """保留模型拒绝原因以供排障，只记录经过脱敏和限长的错误字段。"""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            error = payload.get("error") if isinstance(payload, dict) else None
            details = {}
            if isinstance(error, dict):
                for name in ("type", "code", "param", "message"):
                    value = error.get(name)
                    if isinstance(value, (str, int, float)):
                        text = str(value)
                        if self.config.api_key:
                            text = text.replace(self.config.api_key, "[已隐藏]")
                        details[name] = text[:500]
            logger.error(
                "模型 HTTP 请求失败 provider=%s model=%s status=%s maxTokens=%s "
                "upstreamError=%s",
                self.provider,
                self.config.model,
                response.status_code,
                max_tokens,
                json.dumps(details, ensure_ascii=False),
            )
            raise

    def _usage_from_response(self, data: dict) -> LLMTokenUsage | None:
        """仅在开启真实 usage 的 provider 上解析响应 usage。"""
        if not self.supports_real_usage:
            return None
        return LLMTokenUsage.from_openai_compatible_usage(
            provider=self.provider,
            model=data.get("model") or self.config.model,
            usage=data.get("usage"),
        )

    async def chat_with_usage(self, messages: list[dict]) -> LLMChatResult:
        """非流式对话，返回完整回答文本与可选 token 用量。"""
        turn = await self.complete_turn(messages)
        return LLMChatResult(content=turn.content, usage=turn.usage)

    async def complete_turn(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMAssistantTurn:
        """非流式返回文本、工具调用和需要回传的推理字段。"""
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds(timeout_seconds)
        ) as client:
            response = await client.post(
                self._endpoint(),
                headers=self._headers(),
                json=self._build_body(
                    messages,
                    stream=False,
                    tools=tools,
                    tool_choice=tool_choice,
                    response_format=response_format,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
            )
            self._raise_for_status(response, max_tokens=max_tokens)
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            return LLMAssistantTurn(
                content=message.get("content") or "",
                tool_calls=self._parse_tool_calls(message.get("tool_calls")),
                finish_reason=choice.get("finish_reason"),
                reasoning_content=message.get("reasoning_content"),
                usage=self._usage_from_response(data),
            )

    def _timeout_seconds(self, override: float | None = None) -> float:
        if override is not None:
            return override
        timeout = self.config.extra.get("timeout_seconds", 60)
        try:
            return float(timeout)
        except (TypeError, ValueError):
            return 60.0

    async def stream_chat_with_usage(
        self,
        messages: list[dict],
    ) -> AsyncIterator[LLMStreamChunk]:
        """流式对话，逐片段 yield 文本或 token 用量。"""
        async for event in self.stream_turn(messages):
            if event.content_delta or event.usage:
                yield LLMStreamChunk(
                    content=event.content_delta,
                    usage=event.usage,
                )

    async def stream_turn(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> AsyncIterator[LLMTurnStreamEvent]:
        """流式解析文本、推理内容和按 index 分片的工具参数。"""
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream(
                "POST",
                self._endpoint(),
                headers=self._headers(),
                json=self._build_body(
                    messages,
                    stream=True,
                    tools=tools,
                    tool_choice=tool_choice,
                ),
            ) as response,
        ):
            if not response.is_success:
                await response.aread()
            self._raise_for_status(response)
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                usage = self._usage_from_response(data)
                choices = data.get("choices") or []
                if not choices:
                    if usage:
                        yield LLMTurnStreamEvent(usage=usage)
                    continue
                choice = choices[0]
                delta = choice.get("delta", {})
                yield LLMTurnStreamEvent(
                    content_delta=delta.get("content") or "",
                    reasoning_content_delta=(delta.get("reasoning_content") or ""),
                    tool_call_deltas=self._parse_tool_call_deltas(
                        delta.get("tool_calls")
                    ),
                    finish_reason=choice.get("finish_reason"),
                    usage=usage,
                )

    @staticmethod
    def _parse_tool_calls(raw_calls: list[dict] | None) -> list[LLMToolCall]:
        calls: list[LLMToolCall] = []
        for item in raw_calls or []:
            function = item.get("function") or {}
            arguments = function.get("arguments") or "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            calls.append(
                LLMToolCall(
                    id=str(item.get("id") or ""),
                    name=str(function.get("name") or ""),
                    arguments_json=arguments,
                )
            )
        return calls

    @staticmethod
    def _parse_tool_call_deltas(
        raw_calls: list[dict] | None,
    ) -> list[LLMToolCallDelta]:
        deltas: list[LLMToolCallDelta] = []
        for item in raw_calls or []:
            function = item.get("function") or {}
            deltas.append(
                LLMToolCallDelta(
                    index=int(item.get("index") or 0),
                    id=item.get("id"),
                    name=str(function.get("name") or ""),
                    arguments_delta=str(function.get("arguments") or ""),
                )
            )
        return deltas
