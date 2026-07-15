"""项目上下文模型编排。"""
from __future__ import annotations

from app.core.config import get_settings
from app.llm.factory import get_llm_client
from app.streaming.metrics import LLMChatResult

__all__ = ["ProjectContextModelAgent"]


class ProjectContextModelAgent:
    """项目上下文模型最小调用链路。"""

    def __init__(self, provider: str = "qwen") -> None:
        self.settings = get_settings().llm
        self.client = get_llm_client(provider, self.settings)

    async def generate(self, prompt: str) -> LLMChatResult:
        """使用 Qwen 生成项目上下文分析结果。"""
        return await self.client.chat_with_usage([
            {
                "role": "user",
                "content": prompt,
            }
        ])
