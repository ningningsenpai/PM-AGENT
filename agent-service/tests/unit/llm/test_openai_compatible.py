"""OpenAI 兼容协议、输出额度和错误诊断测试。"""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from app.core.config.llm_config import Settings
from app.llm.clients.deepseek_client import DeepSeekClient
from app.llm.clients.doubao_client import DoubaoClient
from app.llm.structured import StructuredJsonGenerator


@pytest.fixture
def mock_transport(monkeypatch):
    async_client = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: async_client(
                transport=httpx.MockTransport(handler), **kwargs
            ),
        )

    return install


@pytest.fixture
def deepseek_client():
    client = DeepSeekClient(Settings())
    client.config.api_key = "sk-unit-test-secret"
    client.config.model = "deepseek-v4-pro"
    return client


def test_build_body_includes_native_tool_definitions() -> None:
    client = DeepSeekClient(Settings())
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_project",
                "description": "查询项目",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    body = client._build_body(
        [{"role": "user", "content": "查询项目"}],
        False,
        tools=tools,
        tool_choice="auto",
    )

    assert body["tools"] == tools
    assert body["tool_choice"] == "auto"


def test_build_body_includes_structured_output_options() -> None:
    client = DeepSeekClient(Settings())

    body = client._build_body(
        [{"role": "user", "content": "请返回 JSON"}],
        False,
        response_format={"type": "json_object"},
        max_tokens=2048,
        temperature=0,
    )

    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 2048
    assert body["temperature"] == 0
    assert body["thinking"] == {"type": "disabled"}


def test_structured_thinking_override_does_not_affect_chat_tools_or_other_providers():
    deepseek = DeepSeekClient(Settings())
    assert "thinking" not in deepseek._build_body([], False)
    assert "thinking" not in deepseek._build_body([], True)
    tool_body = deepseek._build_body(
        [],
        False,
        response_format={"type": "json_object"},
        tools=[{"type": "function", "function": {"name": "query_project"}}],
    )
    assert "thinking" not in tool_body
    doubao_body = DoubaoClient(Settings())._build_body(
        [], False, response_format={"type": "json_object"}
    )
    assert "thinking" not in doubao_body


def test_parse_tool_calls_keeps_string_id_and_raw_arguments() -> None:
    calls = DeepSeekClient._parse_tool_calls(
        [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "get_current_project",
                    "arguments": "{}",
                },
            }
        ]
    )

    assert calls[0].id == "call-1"
    assert calls[0].arguments_json == "{}"


@pytest.mark.parametrize(
    "model", ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp"]
)
def test_excessive_output_budget_is_rejected_before_http(
    deepseek_client, mock_transport, model
):
    def unexpected_request(request):
        pytest.fail("越界输出额度不应发送到模型服务")

    mock_transport(unexpected_request)
    deepseek_client.config.model = model
    with pytest.raises(RuntimeError, match="max_tokens=409600.*输出上限 384000"):
        asyncio.run(deepseek_client.complete_turn([], max_tokens=409600))

    assert (
        deepseek_client._build_body([], False, max_tokens=384000)["max_tokens"]
        == 384000
    )


@pytest.mark.parametrize("max_tokens", [0, -1, True])
def test_output_budget_must_be_positive_integer(deepseek_client, max_tokens):
    with pytest.raises(RuntimeError, match="max_tokens 必须为正整数"):
        deepseek_client._build_body([], False, max_tokens=max_tokens)


def test_deepseek_limit_does_not_apply_to_unknown_models_or_other_providers(
    deepseek_client,
):
    deepseek_client.config.model = "future-model"
    for client in (deepseek_client, DoubaoClient(Settings())):
        assert client._build_body([], False, max_tokens=409600)["max_tokens"] == 409600


def test_structured_generation_sends_corrected_budget(deepseek_client, mock_transport):
    class Output(BaseModel):
        summary: str

    def handler(request):
        body = json.loads(request.content)
        assert body["max_tokens"] == 4096
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        assert request.extensions["timeout"]["read"] == 120
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"summary":"解析完成"}'},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    mock_transport(handler)
    generator = StructuredJsonGenerator(
        deepseek_client, max_tokens=4096, timeout_seconds=120
    )
    assert asyncio.run(generator.generate("分析测试文本", Output)).summary == "解析完成"


def test_http_error_logs_only_bounded_sanitized_error_fields(
    deepseek_client, mock_transport, caplog
):
    mock_transport(
        lambda request: httpx.Response(
            400,
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_value",
                    "param": "max_tokens",
                    "message": f"错误 {deepseek_client.config.api_key} " + "x" * 800,
                    "debug": "额外的敏感诊断字段",
                },
                "request": "请求中的敏感正文",
            },
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as caught:
        asyncio.run(
            deepseek_client.complete_turn(
                [{"role": "user", "content": "项目文件正文不能写入日志"}],
                max_tokens=4096,
            )
        )

    assert caught.value.response.status_code == 400
    assert "status=400 maxTokens=4096" in caplog.text
    assert "model=deepseek-v4-pro" in caplog.text
    assert deepseek_client.config.api_key not in caplog.text
    assert "额外的敏感诊断字段" not in caplog.text
    assert "请求中的敏感正文" not in caplog.text
    assert "项目文件正文不能写入日志" not in caplog.text
    record = next(
        record for record in caplog.records if "upstreamError=" in record.message
    )
    details = json.loads(record.message.split("upstreamError=", 1)[1])
    assert details["type"] == "invalid_request_error"
    assert details["code"] == "invalid_value"
    assert details["param"] == "max_tokens"
    assert "[已隐藏]" in details["message"]
    assert len(details["message"]) == 500


def test_non_json_error_preserves_http_exception(
    deepseek_client, mock_transport, caplog
):
    mock_transport(lambda request: httpx.Response(502, text="<html>网关错误</html>"))
    with pytest.raises(httpx.HTTPStatusError) as caught:
        asyncio.run(deepseek_client.complete_turn([]))
    assert caught.value.response.status_code == 502
    assert "status=502" in caplog.text
    assert "upstreamError={}" in caplog.text


@pytest.mark.parametrize("status", [400, 302])
def test_stream_error_body_is_read_before_logging(
    deepseek_client, mock_transport, caplog, status
):
    mock_transport(
        lambda request: httpx.Response(
            status,
            stream=httpx.ByteStream(b'{"error":{"message":"invalid request"}}'),
        )
    )

    async def consume():
        return [event async for event in deepseek_client.stream_turn([])]

    with pytest.raises(httpx.HTTPStatusError) as caught:
        asyncio.run(consume())
    assert caught.value.response.status_code == status
    assert "invalid request" in caplog.text
