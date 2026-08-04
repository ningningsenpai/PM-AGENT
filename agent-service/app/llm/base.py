"""LLM 客户端统一协议。

所有具体厂商客户端（DeepSeek、豆包）都必须继承 ``BaseLLMClient`` 并实现
usage-aware 协议；旧的文本协议由基类兼容封装，以便上层 Agent 能按需获取
token 用量，同时保留只取文本的调用方式。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.llm.contracts import (
    LLMAssistantTurn,
    LLMCapabilities,
    LLMTurnStreamEvent,
)
from app.streaming.metrics import LLMChatResult, LLMStreamChunk


class BaseLLMClient(ABC):
    """所有 LLM 客户端必须实现的统一协议。

    类属性 ``provider`` 用作注册表 key，必须与 :mod:`app.core.config`
    中 ``Settings.llm`` 的 provider 名称保持一致，否则工厂无法解析配置。
    """

    # 厂商标识；子类必须重写。例如："deepseek" / "doubao"
    provider: str = ""
    capabilities = LLMCapabilities()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not self.provider:
            raise RuntimeError(
                f"{self.__class__.__name__} 未设置 provider 类属性，无法注册到工厂。"
            )

    @property
    def config(self):
        """当前客户端对应的 provider 配置。"""
        return self.settings.get_llm_config(self.provider)

    async def chat(self, messages: list[dict]) -> str:
        """非流式对话，兼容旧调用方，仅返回完整回答文本。"""
        result = await self.chat_with_usage(messages)
        return result.content

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """流式对话，兼容旧调用方，仅逐 token yield 回答内容。"""
        async for chunk in self.stream_chat_with_usage(messages):
            if chunk.content:
                yield chunk.content

    async def complete_turn(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMAssistantTurn:
        """执行一次完整模型决策；不支持工具的客户端沿用文本协议。"""
        if tools:
            raise RuntimeError(f"模型提供方 {self.provider} 尚未实现原生工具调用")
        result = await self.chat_with_usage(messages)
        return LLMAssistantTurn(content=result.content, usage=result.usage)

    async def stream_turn(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> AsyncIterator[LLMTurnStreamEvent]:
        """流式执行一次模型决策；默认适配既有纯文本流。"""
        if tools:
            raise RuntimeError(f"模型提供方 {self.provider} 尚未实现流式工具调用")
        async for chunk in self.stream_chat_with_usage(messages):
            yield LLMTurnStreamEvent(
                content_delta=chunk.content,
                usage=chunk.usage,
            )

    @abstractmethod
    async def chat_with_usage(self, messages: list[dict]) -> LLMChatResult:
        """非流式对话，返回完整回答文本与可选 token 用量。"""

    @abstractmethod
    async def stream_chat_with_usage(
        self,
        messages: list[dict],
    ) -> AsyncIterator[LLMStreamChunk]:
        """流式对话，逐片段 yield 文本或 token 用量。"""
        if False:  # pragma: no cover
            yield LLMStreamChunk()
