"""Moonshot Kimi 模型适配器。

Kimi 开放平台采用 OpenAI 兼容协议。默认模型 ``moonshot-v1-8k``，
长上下文场景可在 ``.env`` 中切换 ``KIMI_MODEL`` 为 ``moonshot-v1-32k`` 等。

TODO 正式接入前确认：
- 默认模型版本（v1 vs vk vs v2 等正式命名）；
- 是否使用官方 SDK（Moonshot 官方 Python SDK 与 openai 兼容包二选一）。
"""

from app.llm.clients.openai_compatible import OpenAICompatibleClient
from app.llm.registry import register_llm


@register_llm("kimi")
class KimiClient(OpenAICompatibleClient):
    """Moonshot Kimi 模型适配器。"""
