"""项目问答 Agent 原生工具调用编排。"""
from __future__ import annotations

from collections.abc import AsyncIterator
import json

from app.agents.tools import (
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutor,
    ToolRegistry,
)
from app.core.config import Settings
from app.core.errors import AppException, ErrorCode
from app.llm.base import BaseLLMClient
from app.llm.contracts import LLMAssistantTurn, LLMTurnAccumulator, LLMToolCall
from app.llm.factory import get_llm_client
from app.llm.orchestration.context_builder import LLMContextBuilder
from app.llm.prompts.project_chat import build_project_chat_messages
from app.streaming import StreamEventType
from app.streaming.metrics import LLMTokenUsage, LLMTokenUsageSummary
from app.streaming.payloads import (
    AgentChatRequest,
    ChatResponse,
    StreamDonePayload,
    ToolCallPayload,
    ToolCallRecord,
    ToolResultPayload,
)

__all__ = ["ProjectChatAgent"]


class ProjectChatAgent:
    """在有限步数内协调模型决策、工具执行和最终中文回答。"""

    MAX_STEPS = 5
    MAX_TOOL_CALLS = 8

    def __init__(
        self,
        settings: Settings,
        registry: ToolRegistry,
        executor: ToolExecutor,
    ) -> None:
        self.settings = settings
        self._registry = registry
        self._executor = executor

    async def chat(
        self,
        request: AgentChatRequest,
        user_id: int,
    ) -> ChatResponse:
        """执行非流式原生工具调用循环。"""
        llm = self._resolve_llm(request)
        tools = self._tool_definitions(llm, require_streaming=False)
        messages = self._build_messages(request, llm)
        context = self._execution_context(request, user_id)
        records: list[ToolCallRecord] = []
        usage_summary = LLMTokenUsageSummary()
        total_tool_calls = 0

        for _step in range(1, self.MAX_STEPS + 1):
            turn = await llm.complete_turn(
                messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )
            usage_summary.add(turn.usage)
            if not turn.tool_calls:
                if not turn.content:
                    raise AppException(ErrorCode.SYSTEM_ERROR, "模型未返回有效回答")
                return ChatResponse(
                    answer=turn.content,
                    model=llm.config.model,
                    conversation_id=request.conversation_id,
                    tool_calls=records,
                    usage=self._aggregate_usage(llm, request, usage_summary),
                )

            total_tool_calls += len(turn.tool_calls)
            self._check_tool_call_limit(total_tool_calls)
            messages.append(self._assistant_message(turn))
            for call in turn.tool_calls:
                result = await self._executor.execute(call, context)
                records.append(self._public_record(result))
                messages.append(self._tool_message(call, result))

        raise AppException(ErrorCode.AGENT_TOOL_LOOP_LIMIT_EXCEEDED)

    async def stream_chat(
        self,
        request: AgentChatRequest,
        user_id: int,
    ) -> AsyncIterator[dict]:
        """执行流式原生工具调用循环并输出稳定 SSE 业务事件。"""
        llm = self._resolve_llm(request)
        tools = self._tool_definitions(llm, require_streaming=True)
        messages = self._build_messages(request, llm)
        context = self._execution_context(request, user_id)
        usage_summary = LLMTokenUsageSummary()
        total_tool_calls = 0

        for step in range(1, self.MAX_STEPS + 1):
            accumulator = LLMTurnAccumulator()
            async for event in llm.stream_turn(
                messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            ):
                accumulator.add(event)
                if event.content_delta:
                    yield {
                        "event": StreamEventType.TOKEN,
                        "data": event.content_delta,
                    }

            turn = accumulator.build()
            usage_summary.add(turn.usage)
            if not turn.tool_calls:
                if not turn.content:
                    raise AppException(ErrorCode.SYSTEM_ERROR, "模型未返回有效回答")
                yield {
                    "event": StreamEventType.DONE,
                    "data": StreamDonePayload(
                        model=llm.config.model,
                        provider=llm.provider,
                        conversationId=request.conversation_id,
                        usage=self._aggregate_usage(llm, request, usage_summary),
                    ),
                }
                return

            total_tool_calls += len(turn.tool_calls)
            self._check_tool_call_limit(total_tool_calls)
            messages.append(self._assistant_message(turn))
            for call in turn.tool_calls:
                yield {
                    "event": StreamEventType.TOOL_CALL,
                    "data": ToolCallPayload(
                        callId=call.id,
                        toolName=call.name,
                        arguments=self._event_arguments(call),
                        step=step,
                    ),
                }
                result = await self._executor.execute(call, context)
                yield {
                    "event": StreamEventType.TOOL_RESULT,
                    "data": ToolResultPayload(
                        callId=call.id,
                        toolName=call.name,
                        status=result.status,
                        summary=result.public_summary(),
                        errorCode=result.error_code,
                        durationMs=result.duration_ms,
                        step=step,
                    ),
                }
                messages.append(self._tool_message(call, result))

        raise AppException(ErrorCode.AGENT_TOOL_LOOP_LIMIT_EXCEEDED)

    def _resolve_llm(self, request: AgentChatRequest) -> BaseLLMClient:
        provider = request.llm_provider or self.settings.default_llm_provider
        return get_llm_client(provider, self.settings)

    def _tool_definitions(
        self,
        llm: BaseLLMClient,
        *,
        require_streaming: bool,
    ) -> list[dict]:
        tools = self._registry.definitions()
        if tools and not llm.capabilities.native_tool_calling:
            raise AppException(
                ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED,
                f"模型提供方 {llm.provider} 暂不支持原生工具调用",
            )
        if tools and require_streaming and not llm.capabilities.streaming_tool_calling:
            raise AppException(
                ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED,
                f"模型提供方 {llm.provider} 暂不支持流式工具调用",
            )
        return tools

    @staticmethod
    def _build_messages(
        request: AgentChatRequest,
        llm: BaseLLMClient,
    ) -> list[dict]:
        base_messages = LLMContextBuilder(
            request,
            max_context_tokens=llm.config.context_window_tokens,
            reserved_output_tokens=llm.config.reserved_output_tokens,
        ).build()
        return build_project_chat_messages(
            request,
            base_messages=base_messages,
        )

    @staticmethod
    def _execution_context(
        request: AgentChatRequest,
        user_id: int,
    ) -> ToolExecutionContext:
        return ToolExecutionContext(
            user_id=user_id,
            trace_id=request.trace_id,
            conversation_id=request.conversation_id,
            project_id=request.context.project_id,
            iteration_id=request.context.iteration_id,
        )

    @staticmethod
    def _assistant_message(turn: LLMAssistantTurn) -> dict:
        message: dict = {
            "role": "assistant",
            "content": turn.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments_json,
                    },
                }
                for call in turn.tool_calls
            ],
        }
        if turn.reasoning_content:
            message["reasoning_content"] = turn.reasoning_content
        return message

    @staticmethod
    def _tool_message(
        call: LLMToolCall,
        result: ToolExecutionResult,
    ) -> dict:
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "content": result.observation_json(),
        }

    @staticmethod
    def _event_arguments(call: LLMToolCall) -> dict | None:
        try:
            value = json.loads(call.arguments_json or "{}")
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _public_record(result: ToolExecutionResult) -> ToolCallRecord:
        return ToolCallRecord(
            call_id=result.call_id,
            tool_name=result.tool_name,
            input=result.input,
            status=result.status,
            summary=result.public_summary(),
            error_code=result.error_code,
            error_message=result.error_message,
            duration_ms=result.duration_ms,
        )

    def _check_tool_call_limit(self, total_tool_calls: int) -> None:
        if total_tool_calls > self.MAX_TOOL_CALLS:
            raise AppException(ErrorCode.AGENT_TOOL_LOOP_LIMIT_EXCEEDED)

    @staticmethod
    def _aggregate_usage(
        llm: BaseLLMClient,
        request: AgentChatRequest,
        summary: LLMTokenUsageSummary,
    ) -> LLMTokenUsage | None:
        if summary.rounds == 0:
            return None
        return LLMTokenUsage(
            provider=llm.provider,
            model=llm.config.model,
            round_index=request.current_round_index(),
            input_tokens=summary.total_input_tokens,
            output_tokens=summary.total_output_tokens,
            total_tokens=summary.total_tokens,
        )
