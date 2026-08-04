"""DeepSeek 模型适配器。

DeepSeek API 与 OpenAI Chat Completions 协议兼容，
直接复用 :class:`OpenAICompatibleClient` 的公共实现即可。
"""

from app.llm.clients.openai_compatible import OpenAICompatibleClient
from app.llm.contracts import LLMCapabilities
from app.llm.registry import register_llm


@register_llm("deepseek")
class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek 模型适配器；当前默认模型 ``deepseek-v4-pro``。"""

    supports_real_usage = True
    capabilities = LLMCapabilities(
        native_tool_calling=True,
        streaming_tool_calling=True,
        reasoning_content_round_trip=True,
    )
