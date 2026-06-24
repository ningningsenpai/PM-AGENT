"""项目问答 Agent 编排。"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import Settings
from app.llm.base import BaseLLMClient
from app.llm.factory import get_llm_client
from app.llm.orchestration.context_builder import LLMContextBuilder
from app.llm.prompts.project_chat import build_project_chat_messages
from app.llm.tools.demo_project_tool import DemoProjectTool
from app.streaming import StreamEventType
from app.streaming.payloads import AgentChatRequest, ChatResponse, StreamDonePayload, ToolCallRecord

__all__ = ["ProjectChatAgent"]


class ProjectChatAgent:
    """ProjectChatAgent 编排项目问答、上下文构造、工具摘要和模型调用。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.project_tool = DemoProjectTool()

    async def chat(self, request: AgentChatRequest) -> ChatResponse:
        """执行非流式项目问答。"""
        llm = self._resolve_llm(request)
        tool_calls = self._maybe_call_tools(request)
        base_messages = LLMContextBuilder(
            request,
            max_context_tokens=llm.config.context_window_tokens,
            reserved_output_tokens=llm.config.reserved_output_tokens,
        ).build()
        messages = build_project_chat_messages(
            request,
            self._tool_summary(tool_calls),
            base_messages=base_messages,
        )
        result = await llm.chat_with_usage(messages)
        usage = result.usage.model_copy(
            update={"round_index": result.usage.round_index or request.current_round_index()}
        ) if result.usage else None
        return ChatResponse(
            answer=result.content,
            model=llm.config.model,
            conversation_id=request.conversation_id,
            tool_calls=tool_calls,
            usage=usage,
        )

    async def stream_chat(self, request: AgentChatRequest) -> AsyncIterator[dict]:
        """执行流式项目问答，按 SSE 事件返回工具调用与 token。"""
        llm = self._resolve_llm(request)
        tool_calls = self._maybe_call_tools(request)

        for tool_call in tool_calls:
            yield {"event": StreamEventType.TOOL_CALL, "data": tool_call.model_dump()}

        base_messages = LLMContextBuilder(
            request,
            max_context_tokens=llm.config.context_window_tokens,
            reserved_output_tokens=llm.config.reserved_output_tokens,
        ).build()
        messages = build_project_chat_messages(
            request,
            self._tool_summary(tool_calls),
            base_messages=base_messages,
        )
        usage = None
        async for chunk in llm.stream_chat_with_usage(messages):
            if chunk.content:
                yield {"event": StreamEventType.TOKEN, "data": chunk.content}
            if chunk.usage:
                usage = chunk.usage.model_copy(
                    update={"round_index": chunk.usage.round_index or request.current_round_index()}
                )

        yield {
            "event": StreamEventType.DONE,
            "data": StreamDonePayload(
                model=llm.config.model,
                provider=llm.provider,
                conversationId=request.conversation_id,
                usage=usage,
            ),
        }

    def _resolve_llm(self, request: AgentChatRequest) -> BaseLLMClient:
        provider = request.llm_provider or self.settings.default_llm_provider
        return get_llm_client(provider, self.settings)

    def _maybe_call_tools(self, request: AgentChatRequest) -> list[ToolCallRecord]:
        last_user_text = request.last_user_message()
        if request.use_tool_demo or "项目" in last_user_text or "任务" in last_user_text:
            return [self.project_tool.run(request.context.project_id)]
        return []

    def _tool_summary(self, tool_calls: list[ToolCallRecord]) -> str | None:
        if not tool_calls:
            return None
        first_output = tool_calls[0].output
        return (
            f"项目名称：{first_output['project_name']}；"
            f"状态：{first_output['status']}；"
            f"任务统计：{first_output['task_summary']}；"
            f"风险摘要：{first_output['risk_summary']}"
        )
