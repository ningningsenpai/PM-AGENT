"""项目上下文结构化模型生成器测试。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from pydantic import BaseModel

from app.llm.contracts import LLMAssistantTurn
from app.project.context.model.structured import StructuredJsonGenerator


class _Payload(BaseModel):
    name: str


class StructuredJsonGeneratorTest(IsolatedAsyncioTestCase):
    async def test_generate_requests_deepseek_json_mode(self) -> None:
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content='{"name":"项目文件"}',
                    finish_reason="stop",
                )
            )
        )
        generator = StructuredJsonGenerator(
            client,
            max_tokens=2048,
            timeout_seconds=45,
        )

        result = await generator.generate("请分析并返回 JSON", _Payload)

        self.assertEqual("项目文件", result.name)
        _, kwargs = client.complete_turn.await_args
        self.assertEqual({"type": "json_object"}, kwargs["response_format"])
        self.assertEqual(2048, kwargs["max_tokens"])
        self.assertEqual(0, kwargs["temperature"])
        self.assertEqual(45, kwargs["timeout_seconds"])

    async def test_generate_rejects_truncated_response(self) -> None:
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content='{"name":"未完成',
                    finish_reason="length",
                )
            )
        )
        generator = StructuredJsonGenerator(
            client,
            max_tokens=128,
            timeout_seconds=30,
        )

        with self.assertRaisesRegex(ValueError, "结果不完整"):
            await generator.generate("请返回 JSON", _Payload)

    async def test_generate_rejects_empty_response(self) -> None:
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(content="", finish_reason="stop")
            )
        )
        generator = StructuredJsonGenerator(
            client,
            max_tokens=128,
            timeout_seconds=30,
        )

        with self.assertRaisesRegex(ValueError, "未返回结构化 JSON"):
            await generator.generate("请返回 JSON", _Payload)

