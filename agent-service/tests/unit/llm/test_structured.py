"""项目上下文结构化模型生成器测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from pydantic import BaseModel

from app.llm.contracts import LLMAssistantTurn
from app.llm.structured import (
    StructuredJsonGenerator,
    StructuredOutputError,
    StructuredOutputTruncatedError,
)


class _Payload(BaseModel):
    name: str


class StructuredJsonGeneratorTest(IsolatedAsyncioTestCase):
    async def test_optional_normalization_does_not_bypass_model_validation(self) -> None:
        client = SimpleNamespace(complete_turn=AsyncMock(return_value=LLMAssistantTurn(
            content='{"other":"项目文件"}', finish_reason="stop",
        )))
        generator = StructuredJsonGenerator(client, max_tokens=2048, timeout_seconds=45)
        with self.assertRaises(StructuredOutputError):
            await generator.generate("请返回 JSON", _Payload)
        result = await generator.generate(
            "请返回 JSON", _Payload, normalize_json=lambda _: '{"name":"项目文件"}',
        )
        self.assertEqual("项目文件", result.name)
        with self.assertRaises(StructuredOutputError):
            await generator.generate(
                "请返回 JSON", _Payload, normalize_json=lambda _: '{"name":[]}',
            )
        self.assertEqual(3, client.complete_turn.await_count)

    async def test_truncated_or_empty_output_is_not_normalized(self) -> None:
        for turn in (
            LLMAssistantTurn(content='{"name":"截断内容"}', finish_reason="length"),
            LLMAssistantTurn(content="", finish_reason="stop"),
        ):
            with self.subTest(turn=turn):
                client = SimpleNamespace(complete_turn=AsyncMock(return_value=turn))
                generator = StructuredJsonGenerator(client, max_tokens=2048, timeout_seconds=45)
                normalize = Mock(return_value='{"name":"不应修复"}')
                with self.assertRaises(StructuredOutputError):
                    await generator.generate("请返回 JSON", _Payload, normalize_json=normalize)
                normalize.assert_not_called()

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

        with self.assertRaisesRegex(StructuredOutputTruncatedError, "结果不完整"):
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

    async def test_truncation_diagnostics_do_not_log_content_or_reasoning(self) -> None:
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content="未完成的敏感正文",
                    reasoning_content="模型内部推理内容",
                    finish_reason="length",
                )
            )
        )
        generator = StructuredJsonGenerator(
            client, max_tokens=4096, timeout_seconds=120
        )

        with (
            self.assertLogs("app.llm.structured", level="INFO") as logs,
            self.assertRaisesRegex(StructuredOutputError, "max_tokens=4096"),
        ):
            await generator.generate("项目文件原文", _Payload)

        text = "\n".join(logs.output)
        self.assertIn("finishReason=length", text)
        self.assertNotIn("未完成的敏感正文", text)
        self.assertNotIn("模型内部推理内容", text)
        self.assertNotIn("项目文件原文", text)

    async def test_validation_diagnostics_omit_input_values(self) -> None:
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content='{"name":{"secret":"敏感字段值"}}',
                    finish_reason="stop",
                )
            )
        )
        generator = StructuredJsonGenerator(
            client, max_tokens=4096, timeout_seconds=120
        )

        with (
            self.assertLogs("app.llm.structured", level="WARNING") as logs,
            self.assertRaisesRegex(StructuredOutputError, "不符合字段要求"),
        ):
            await generator.generate("请返回 JSON", _Payload)

        text = "\n".join(logs.output)
        self.assertIn("name", text)
        self.assertIn("string_type", text)
        self.assertIn('"inputType": "dict"', text)
        self.assertNotIn("敏感字段值", text)
        self.assertNotIn("secret", text)
