"""项目问答 Agent 原生工具调用测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.agents.tools import ToolExecutor, ToolRegistry
from app.agents.tools.project import GetCurrentProjectTool
from app.core.errors import AppException, ErrorCode
from app.input_context import (
    RetrievalEvidence,
    RetrievalHit,
    RetrievalResult,
    UserInputContext,
    create_default_normalization_service,
)
from app.llm.contracts import (
    LLMAssistantTurn,
    LLMCapabilities,
    LLMToolCall,
    LLMToolCallDelta,
    LLMTurnStreamEvent,
)
from app.llm.orchestration.project_chat_agent import ProjectChatAgent
from app.modules.project.schemas import ProjectResponse
from app.streaming import StreamEventType
from app.streaming.metrics import LLMTokenUsage
from app.streaming.payloads import AgentChatRequest


class FakeLLM:
    provider = "deepseek"
    capabilities = LLMCapabilities(
        native_tool_calling=True,
        streaming_tool_calling=True,
    )

    def __init__(self) -> None:
        self.config = SimpleNamespace(
            model="deepseek-test",
            context_window_tokens=4096,
            reserved_output_tokens=512,
        )
        self.turns: list[LLMAssistantTurn] = []
        self.streams: list[list[LLMTurnStreamEvent]] = []
        self.requests: list[list[dict]] = []

    async def complete_turn(self, messages, **_kwargs) -> LLMAssistantTurn:
        self.requests.append(deepcopy(messages))
        return self.turns.pop(0)

    async def stream_turn(
        self, messages, **_kwargs
    ) -> AsyncIterator[LLMTurnStreamEvent]:
        self.requests.append(deepcopy(messages))
        for event in self.streams.pop(0):
            yield event


def _request(*, stream: bool = False) -> AgentChatRequest:
    return AgentChatRequest.model_validate(
        {
            "trace_id": "trace-1",
            "conversation_id": 20,
            "messages": [{"role": "user", "content": "当前项目是什么？"}],
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
            "stream": stream,
        }
    )


def _agent(llm: FakeLLM):
    now = datetime(2026, 8, 3, 10, 0, 0, tzinfo=UTC)
    projects = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=ProjectResponse(
                id=10,
                project_name="PM-Agent",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    )
    registry = ToolRegistry([GetCurrentProjectTool(projects)])
    settings = SimpleNamespace(default_llm_provider="deepseek")
    agent = ProjectChatAgent(settings, registry, ToolExecutor(registry))
    return agent, projects


class TestProjectChatAgent(IsolatedAsyncioTestCase):
    async def test_chat_injects_pre_retrieval_before_first_model_turn(self) -> None:
        llm = FakeLLM()
        llm.turns = [LLMAssistantTurn(content="项目当前完成度约为 50%。")]
        agent, _projects = _agent(llm)
        gateway = SimpleNamespace(
            prepare=AsyncMock(
                return_value=UserInputContext(
                    raw_query="当前项目是什么？",
                    normalization=create_default_normalization_service().normalize_query(
                        "当前完成度"
                    ),
                    retrieval=RetrievalResult(
                        query="当前项目是什么？",
                        hits=[
                            RetrievalHit(
                                source_type="project_specification",
                                source_id="development-stage",
                                title="项目开发阶段",
                                summary="阶段一基础档案已完成，整体约 50%",
                                score=10,
                                evidence=[
                                    RetrievalEvidence(
                                        text="阶段一基础档案已完成，整体约 50%",
                                        logical_path="docs/开发文档.md",
                                    )
                                ],
                            )
                        ],
                    ),
                )
            ),
        )
        agent._input_context_gateway = gateway

        with patch(
            "app.llm.orchestration.project_chat_agent.get_llm_client",
            return_value=llm,
        ):
            response = await agent.chat(_request(), 1)

        self.assertEqual("项目当前完成度约为 50%。", response.answer)
        gateway.prepare.assert_awaited_once()
        retrieval_message = next(
            message
            for message in llm.requests[0]
            if message["role"] == "system"
            and "项目上下文前置召回结果" in message["content"]
        )
        self.assertIn("docs/开发文档.md", retrieval_message["content"])
        self.assertIn("项目进度", retrieval_message["content"])
        self.assertNotIn("stage_durations_ms", retrieval_message["content"])

    async def test_chat_executes_native_tool_and_returns_final_answer(self) -> None:
        llm = FakeLLM()
        llm.turns = [
            LLMAssistantTurn(
                tool_calls=[
                    LLMToolCall(
                        id="call-1",
                        name="get_current_project",
                        arguments_json="{}",
                    )
                ]
            ),
            LLMAssistantTurn(
                content="当前项目是 PM-Agent。",
                usage=LLMTokenUsage(
                    provider="deepseek",
                    input_tokens=10,
                    output_tokens=5,
                ),
            ),
        ]
        agent, projects = _agent(llm)

        with patch(
            "app.llm.orchestration.project_chat_agent.get_llm_client",
            return_value=llm,
        ):
            response = await agent.chat(_request(), 1)

        self.assertEqual(response.answer, "当前项目是 PM-Agent。")
        self.assertEqual(response.tool_calls[0].tool_name, "get_current_project")
        self.assertEqual(response.tool_calls[0].output, {})
        projects.get_owned.assert_awaited_once_with(1, 10)
        self.assertEqual(llm.requests[1][-1]["role"], "tool")

    async def test_stream_chat_emits_tool_events_before_final_token(self) -> None:
        llm = FakeLLM()
        llm.streams = [
            [
                LLMTurnStreamEvent(
                    tool_call_deltas=[
                        LLMToolCallDelta(
                            index=0,
                            id="call-1",
                            name="get_current_project",
                            arguments_delta="{}",
                        )
                    ],
                    finish_reason="tool_calls",
                )
            ],
            [
                LLMTurnStreamEvent(content_delta="当前项目是 PM-Agent。"),
                LLMTurnStreamEvent(finish_reason="stop"),
            ],
        ]
        agent, _projects = _agent(llm)

        with patch(
            "app.llm.orchestration.project_chat_agent.get_llm_client",
            return_value=llm,
        ):
            events = [
                event async for event in agent.stream_chat(_request(stream=True), 1)
            ]

        self.assertEqual(
            [event["event"] for event in events],
            [
                StreamEventType.TOOL_CALL,
                StreamEventType.TOOL_RESULT,
                StreamEventType.TOKEN,
                StreamEventType.DONE,
            ],
        )

    async def test_chat_rejects_provider_without_native_tools(self) -> None:
        llm = FakeLLM()
        llm.provider = "qwen"
        llm.capabilities = LLMCapabilities()
        agent, _projects = _agent(llm)

        with (
            patch(
                "app.llm.orchestration.project_chat_agent.get_llm_client",
                return_value=llm,
            ),
            self.assertRaises(AppException) as caught,
        ):
            await agent.chat(_request(), 1)

        self.assertIs(caught.exception.error, ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED)

    async def test_stream_rejects_provider_without_streaming_tools(self) -> None:
        llm = FakeLLM()
        llm.capabilities = LLMCapabilities(native_tool_calling=True)
        agent, _projects = _agent(llm)

        with (
            patch(
                "app.llm.orchestration.project_chat_agent.get_llm_client",
                return_value=llm,
            ),
            self.assertRaises(AppException) as caught,
        ):
            _events = [
                event async for event in agent.stream_chat(_request(stream=True), 1)
            ]

        self.assertIs(caught.exception.error, ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED)
