"""项目问答 Agent 原生工具调用编排。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.agents.retrieval import AgentInputContextGateway
from app.agents.tools import (
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutor,
    ToolRegistry,
)
from app.core.config import Settings
from app.core.errors import AppException, ErrorCode
from app.input_context import UserInputContext
from app.llm.base import BaseLLMClient
from app.llm.contracts import LLMAssistantTurn, LLMToolCall, LLMTurnAccumulator
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

    def tool_catalog(self) -> list[dict]:
        """目录由实际请求级注册表生成，保持定义与可执行实现一致。"""
        return self._registry.definitions()

    def __init__(
        self,
        settings: Settings,
        registry: ToolRegistry,
        executor: ToolExecutor,
        input_context_gateway: AgentInputContextGateway | None = None,
    ) -> None:
        self.settings = settings
        self._registry = registry
        self._executor = executor
        self._input_context_gateway = input_context_gateway

    async def chat(
        self,
        request: AgentChatRequest,
        user_id: int,
        *,
        history: list[dict] | None = None,
        protocol_out: list[dict] | None = None,
        run_id: int | None = None,
    ) -> ChatResponse:
        """执行非流式原生工具调用循环。"""
        llm = self._resolve_llm(request)
        allowed_tools = self._allowed_tool_names(request)
        tools = self._tool_definitions(llm, allowed_tools)
        context = self._execution_context(request, user_id, run_id=run_id)
        input_context = await self._prepare_input_context(request, context)
        messages = self._build_messages(request, llm, input_context)
        if history is not None:
            messages = (
                [message for message in messages if message["role"] == "system"]
                + history
                + [{"role": "user", "content": request.messages[-1].content}]
            )
        protocol_start = len(messages) - 1
        records: list[ToolCallRecord] = []
        usage_summary = LLMTokenUsageSummary()
        total_tool_calls = 0

        for _step in range(1, self.MAX_STEPS + 1):
            if self._input_context_gateway is not None:
                await self._input_context_gateway.release_reads()
            self._fit_history(messages, llm, tools)
            if protocol_out is not None:
                protocol_start = max(
                    index
                    for index, message in enumerate(messages)
                    if message["role"] == "user"
                )
            turn = await llm.complete_turn(
                messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
                max_tokens=getattr(self.settings, "chat_max_tokens", 16384),
            )
            usage_summary.add(turn.usage)
            if turn.finish_reason == "length":
                raise AppException(
                    ErrorCode.SYSTEM_ERROR, "模型回答达到输出上限，未生成完整结果"
                )
            if not turn.tool_calls:
                if not turn.content.strip():
                    raise AppException(ErrorCode.SYSTEM_ERROR, "模型未返回有效回答")
                if protocol_out is not None:
                    protocol_out.extend(messages[protocol_start:])
                    protocol_out.append(
                        {
                            "role": "assistant",
                            "content": turn.content,
                            **(
                                {"reasoning_content": turn.reasoning_content}
                                if turn.reasoning_content is not None
                                else {}
                            ),
                        }
                    )
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
                result = await self._executor.execute(
                    call,
                    context,
                    allowed_tools=allowed_tools,
                )
                from app.llm.telemetry import record_tool

                record_tool(_step, result)
                records.append(self._public_record(result))
                messages.append(self._tool_message(call, result))

        raise AppException(ErrorCode.AGENT_TOOL_LOOP_LIMIT_EXCEEDED)

    def _fit_history(self, messages, llm, tools):
        """以本次实际消息重新计量，按完整用户轮次移除较早的协议组。"""
        from app.llm.telemetry import input_upper_bound

        limit = llm.config.context_window_tokens
        maximum = getattr(self.settings, "chat_max_tokens", 16384)
        if not limit:
            return
        while (
            input_upper_bound(
                {
                    "model": llm.config.model,
                    "messages": messages,
                    "tools": tools,
                    "max_tokens": maximum,
                }
            )
            + maximum
            > limit
        ):
            users = [
                index for index, item in enumerate(messages) if item["role"] == "user"
            ]
            if len(users) < 2:
                raise AppException(
                    ErrorCode.PARAM_INVALID,
                    "当前问题和工具结果超过上下文预算，请缩小问题范围",
                )
            del messages[users[0] : users[1]]

    async def stream_chat(
        self,
        request: AgentChatRequest,
        user_id: int,
    ) -> AsyncIterator[dict]:
        """执行流式原生工具调用循环并输出稳定 SSE 业务事件。"""
        llm = self._resolve_llm(request)
        allowed_tools = self._allowed_tool_names(request)
        tools = self._tool_definitions(llm, allowed_tools)
        if tools and not llm.capabilities.streaming_tool_calling:
            raise AppException(
                ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED,
                f"模型提供方 {llm.provider} 暂不支持流式工具调用",
            )
        context = self._execution_context(request, user_id)
        input_context = await self._prepare_input_context(request, context)
        messages = self._build_messages(request, llm, input_context)
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
                if not turn.content.strip():
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
                result = await self._executor.execute(
                    call,
                    context,
                    allowed_tools=allowed_tools,
                )
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
        allowed_tools: set[str] | None = None,
    ) -> list[dict]:
        tools = self._registry.definitions(allowed_tools)
        if tools and not llm.capabilities.native_tool_calling:
            raise AppException(
                ErrorCode.LLM_TOOL_CALLING_UNSUPPORTED,
                f"模型提供方 {llm.provider} 暂不支持原生工具调用",
            )
        return tools

    @staticmethod
    def _allowed_tool_names(request: AgentChatRequest) -> set[str]:
        """依据后端计划收缩工具；计划缺失或损坏时只开放只读能力。"""

        plan = request.context.request_plan
        if not isinstance(plan, dict):
            return ProjectChatAgent._safe_read_only_tools()
        if plan.get("requires_clarification") is True:
            return ProjectChatAgent._safe_read_only_tools()
        raw_units = plan.get("request_units")
        if not isinstance(raw_units, list):
            return ProjectChatAgent._safe_read_only_tools()
        actions = {
            item.get("action")
            for item in raw_units
            if isinstance(item, dict) and isinstance(item.get("action"), str)
        }
        allowed = {"get_current_project"}
        mapping = {
            "answer_project_question": {
                "retrieve_project_context",
                "list_current_project_files",
            },
            "analyze_project_progress": {
                "retrieve_project_context",
                "list_current_project_files",
                "get_project_report",
            },
            "draft_next_stage_tasks": {
                "retrieve_project_context",
                "list_context_entries",
            },
            "analyze_project_risks": {
                "retrieve_project_context",
                "list_current_project_files",
                "read_project_file_evidence",
            },
            "check_project_constraints": {
                "retrieve_project_context",
                "list_context_entries",
                "list_current_project_files",
                "read_project_file_evidence",
            },
            "trace_information_source": {
                "retrieve_project_context",
                "list_current_project_files",
                "read_project_file_evidence",
                "get_context_changes",
            },
            "explain_project_history": {
                "retrieve_project_context",
                "list_context_entries",
                "get_context_changes",
                "get_project_report",
            },
        }
        for action in actions:
            allowed.update(mapping.get(action, set()))
        if plan.get("context_updates"):
            allowed.update({"list_context_entries", "get_context_changes"})
        return allowed

    @staticmethod
    def _safe_read_only_tools() -> set[str]:
        """兼容请求的安全基线不包含任何草稿生成能力。"""

        return {
            "get_current_project",
            "list_owned_projects",
            "retrieve_project_context",
            "list_current_project_files",
            "list_context_entries",
            "get_context_changes",
            "get_project_report",
            "read_project_file_evidence",
        }

    @staticmethod
    def _build_messages(
        request: AgentChatRequest,
        llm: BaseLLMClient,
        input_context: UserInputContext | None = None,
    ) -> list[dict]:
        base_messages = LLMContextBuilder(
            request,
            max_context_tokens=llm.config.context_window_tokens,
            reserved_output_tokens=llm.config.reserved_output_tokens,
        ).build()
        return build_project_chat_messages(
            request,
            base_messages=base_messages,
            input_context=input_context,
        )

    async def _prepare_input_context(
        self,
        request: AgentChatRequest,
        context: ToolExecutionContext,
    ) -> UserInputContext | None:
        """在首次模型判断前归一化当前问题并执行轻量召回。"""
        if self._input_context_gateway is None or context.project_id is None:
            return None
        current_question = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role == "user"
            ),
            "",
        )
        if not current_question.strip():
            return None
        return await self._input_context_gateway.prepare(context, current_question)

    @staticmethod
    def _execution_context(
        request: AgentChatRequest,
        user_id: int,
        *,
        run_id: int | None = None,
    ) -> ToolExecutionContext:
        return ToolExecutionContext(
            user_id=user_id,
            trace_id=request.trace_id,
            conversation_id=request.conversation_id,
            project_id=request.context.project_id,
            iteration_id=request.context.iteration_id,
            run_id=run_id,
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
