"""Agent 请求工具消息边界测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.streaming.payloads import AgentChatRequest


def test_request_rejects_client_supplied_tool_history() -> None:
    payload = {
        "trace_id": "trace-1",
        "conversation_id": 20,
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "get_current_project",
                        "arguments": {},
                    }
                ],
            },
            {
                "role": "tool",
                "content": '{"status":"success"}',
                "tool_call_id": "call-1",
            },
            {"role": "user", "content": "继续"},
        ],
        "context": {
            "project_id": 10,
            "iteration_id": 0,
            "context_total_usage": 0,
            "task_id": 0,
        },
        "user": {
            "user_id": 1,
            "tenant_id": 0,
            "user_name": "测试用户",
        },
    }

    with pytest.raises(ValidationError, match="客户端不得提交工具调用或工具结果消息"):
        AgentChatRequest.model_validate(payload)
