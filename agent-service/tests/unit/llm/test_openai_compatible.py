"""OpenAI 兼容工具协议测试。"""

from app.core.config.llm_config import Settings
from app.llm.clients.deepseek_client import DeepSeekClient


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
