import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings


class DeepSeekClient:
    """DeepSeek V4-pro 模型适配器。

    未配置 DEEPSEEK_API_KEY 时进入 Demo 模式，避免初次运行必须依赖真实模型 Key。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(self, messages: list[dict[str, str]]) -> str:
        if self.settings.demo_mode:
            return self._demo_answer(messages)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                json={
                    "model": self.settings.deepseek_model,
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        if self.settings.demo_mode:
            answer = self._demo_answer(messages)
            for part in answer.split("，"):
                yield part + "，"
            return

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                json={
                    "model": self.settings.deepseek_model,
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line.removeprefix("data: ").strip()
                    if payload == "[DONE]":
                        break
                    data = json.loads(payload)
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content

    def _demo_answer(self, messages: list[dict[str, str]]) -> str:
        user_content = messages[-1]["content"] if messages else ""
        return (
            "这是 DeepSeek V4-pro Demo 模式回答。"
            "当前没有配置真实 DEEPSEEK_API_KEY，所以我不会调用外部模型。"
            "从运转规则看，Java 负责认证、权限和业务数据，Python 负责 Prompt 编排、模型调用和工具选择。"
            f"本次收到的问题摘要：{user_content[-80:]}"
        )
