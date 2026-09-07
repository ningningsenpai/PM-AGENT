"""工具协议、失败保留、次数限制和历史压缩的确定性测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.agents.tools import ToolExecutionContext, ToolExecutor, ToolRegistry
from app.agents.tools.context import (
    GetContextChangesTool,
    ListContextEntriesTool,
    ReadProjectFileEvidenceTool,
)
from app.core.errors import AppException
from app.llm.contracts import LLMAssistantTurn, LLMToolCall
from app.llm.telemetry import capture_calls

from tests.unit.agents.test_project_chat_agent import FakeLLM, _agent, _request

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def call(index=1, name="get_current_project", arguments="{}"):
    return LLMToolCall(id=f"c{index}", name=name, arguments_json=arguments)


def test_duplicate_call_ids_are_rejected():
    with pytest.raises(ValueError, match="重复"):
        LLMAssistantTurn(tool_calls=[call(1), call(1)])


async def test_empty_answer_is_not_success():
    llm = FakeLLM()
    llm.turns = [LLMAssistantTurn(content="  \n")]
    agent, _ = _agent(llm)
    with patch.object(agent, "_resolve_llm", return_value=llm), pytest.raises(AppException, match="有效回答"):
        await agent.chat(_request(), 1)


async def test_multiple_steps_and_protocol_history_roundtrip():
    llm = FakeLLM()
    llm.turns = [
        LLMAssistantTurn(
            tool_calls=[call(1), call(2)], reasoning_content="检查两个查询"
        ),
        LLMAssistantTurn(tool_calls=[call(3)]),
        LLMAssistantTurn(content="已核实"),
    ]
    agent, _ = _agent(llm)
    events, protocol = [], []
    with patch.object(agent, "_resolve_llm", return_value=llm), capture_calls(events):
        await agent.chat(_request(), 1, history=[], protocol_out=protocol)
    assert [item["tool_call_id"] for item in protocol if item["role"] == "tool"] == [
        "c1",
        "c2",
        "c3",
    ]
    assert protocol[1]["reasoning_content"] == "检查两个查询"
    assert len(events) == 3 and all(item["status"] == "success" for item in events)
    llm.turns = [LLMAssistantTurn(content="再次核实完成")]
    with patch.object(agent, "_resolve_llm", return_value=llm):
        await agent.chat(_request(), 1, history=protocol)
    request = llm.requests[-1]
    assert [item["tool_call_id"] for item in request if item["role"] == "tool"] == [
        "c1",
        "c2",
        "c3",
    ]


async def test_tool_success_then_model_failure_preserves_tool_event():
    llm = FakeLLM()
    llm.turns = [
        LLMAssistantTurn(tool_calls=[call()]),
        LLMAssistantTurn(content="半份结果", finish_reason="length"),
    ]
    agent, _ = _agent(llm)
    events = []
    with (
        patch.object(agent, "_resolve_llm", return_value=llm),
        capture_calls(events),
        pytest.raises(AppException, match="输出上限"),
    ):
        await agent.chat(_request(), 1)
    assert len(events) == 1 and events[0]["status"] == "success"


@pytest.mark.parametrize("batch_size,rounds", [(9, 1), (1, 5)])
async def test_tool_and_step_limits(batch_size, rounds):
    llm = FakeLLM()
    llm.turns = [
        LLMAssistantTurn(tool_calls=[call(index) for index in range(batch_size)])
        for _ in range(rounds)
    ]
    agent, _ = _agent(llm)
    with (
        patch.object(agent, "_resolve_llm", return_value=llm),
        pytest.raises(AppException),
    ):
        await agent.chat(_request(), 1)


async def test_unknown_tool_and_invalid_identity_have_linked_failure():
    context = ToolExecutionContext(1, "t", 1, 11)
    executor = ToolExecutor(ToolRegistry([ListContextEntriesTool(SimpleNamespace())]))
    invalid = await executor.execute(
        call(1, "list_context_entries", '{"user_id":2}'), context
    )
    unknown = await executor.execute(call(2, "delete_project"), context)
    assert invalid.call_id == "c1" and invalid.error_code == "TOOL_ARGUMENT_INVALID"
    assert unknown.call_id == "c2" and unknown.error_code == "TOOL_NOT_REGISTERED"


async def test_timeout_and_no_data():
    async def waiting(*args, **kwargs):
        await asyncio.sleep(0.1)

    slow = ListContextEntriesTool(SimpleNamespace(list_entries=waiting))
    slow.timeout_seconds = 0.01
    executor = ToolExecutor(ToolRegistry([slow]))
    result = await executor.execute(
        call(1, slow.name), ToolExecutionContext(1, "t", 1, 11)
    )
    assert result.error_code == "TOOL_EXECUTION_TIMEOUT"

    async def empty(*args, **kwargs):
        return []

    slow.service.list_entries = empty
    result = await executor.execute(
        call(2, slow.name), ToolExecutionContext(1, "t", 1, 11)
    )
    assert result.status == "success" and result.output == {"entries": []}


async def test_history_compaction_drops_complete_tool_group():
    llm = FakeLLM()
    agent, _ = _agent(llm)
    agent.settings.chat_max_tokens = 100
    llm.config.context_window_tokens = 2200
    messages = [
        {"role": "system", "content": "中文回答"},
        {"role": "user", "content": "旧问题"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "old",
                    "function": {"name": "get_current_project", "arguments": "{}"},
                    "type": "function",
                }
            ],
        },
        {"role": "tool", "tool_call_id": "old", "content": "旧数据" * 1000},
        {"role": "assistant", "content": "旧回答"},
        {"role": "user", "content": "新问题"},
    ]
    agent._fit_history(messages, llm, [])
    assert [message["role"] for message in messages] == ["system", "user"]


async def test_evidence_tool_rejects_paths_and_context_override():
    tool = ReadProjectFileEvidenceTool(SimpleNamespace())
    context = ToolExecutionContext(1, "t", 1, 11)
    executor = ToolExecutor(
        ToolRegistry([tool, GetContextChangesTool(SimpleNamespace())])
    )
    for name, payload in [
        (tool.name, '{"file_id":1,"path":"C:/private"}'),
        ("get_context_changes", '{"entry_id":"1","project_id":"21"}'),
    ]:
        result = await executor.execute(call(1, name, payload), context)
        assert result.error_code == "TOOL_ARGUMENT_INVALID"
