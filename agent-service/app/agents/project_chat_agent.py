from collections.abc import AsyncIterator

from app.core.config import Settings
from app.llm.base import BaseLLMClient
from app.llm.context.builder import LLMContextBuilder
from app.llm.factory import get_llm_client
from app.prompts.project_chat import build_project_chat_messages
from app.schemas.chat import ChatResponse, ToolCallRecord
from app.streaming import StreamEventType
from app.streaming.payloads import AgentChatRequest
from app.tools.demo_project_tool import DemoProjectTool


class ProjectChatAgent:
    """项目问答 Agent，支持多轮对话。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.project_tool = DemoProjectTool()

    def _resolve_llm(self, request: AgentChatRequest) -> BaseLLMClient:
        """按请求字段或服务端默认值解析具体的 LLM 客户端。"""
        provider = request.llm_provider or self.settings.default_llm_provider
        return get_llm_client(provider, self.settings)

    async def chat(self, request: AgentChatRequest) -> ChatResponse:
        """非流式多轮对话。"""
        llm = self._resolve_llm(request)
        tool_calls = self._maybe_call_tools(request)
        base_messages = LLMContextBuilder(
            request,
            max_context_tokens=llm.config.context_window_tokens,
            reserved_output_tokens=llm.config.reserved_output_tokens,
        ).build()
        print(base_messages)
        messages = build_project_chat_messages(
            request,
            self._tool_summary(tool_calls),
            base_messages=base_messages,
        )
        print(messages)
        result = await llm.chat_with_usage(messages)
        usage = request.record_token_usage(result.usage)
        return ChatResponse(
            answer=result.content,
            model=llm.config.model,
            conversation_id=request.conversation_id,
            tool_calls=tool_calls,
            usage=usage,
            usage_summary=request.current_token_usage_summary(),
        )

    async def stream_chat(self, request: AgentChatRequest) -> AsyncIterator[dict]:
        """流式多轮对话；按事件 yield 工具调用与 token。"""
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
                usage = request.record_token_usage(chunk.usage)

        yield {
            "event": StreamEventType.DONE,
            "data": {
                "model": llm.config.model,
                "provider": llm.provider,
                "conversationId": request.conversation_id,
                "usage": usage.model_dump() if usage else None,
                "usageSummary": request.current_token_usage_summary().model_dump(),
            },
        }

    def _maybe_call_tools(self, request: AgentChatRequest) -> list[ToolCallRecord]:
        """根据最后一条用户输入决定是否调用 Demo 工具。"""
        last_user_text = request.last_user_message()
        if request.use_tool_demo or "项目" in last_user_text or "任务" in last_user_text:
            return [self.project_tool.run(request.context.project_id)]
        return []

    def _tool_summary(self, tool_calls: list[ToolCallRecord]) -> str | None:
        """把第一次工具调用的输出拼成自然语言摘要，注入下一轮 system 提示。"""
        if not tool_calls:
            return None
        first_output = tool_calls[0].output
        return (
            f"项目名称：{first_output['project_name']}；"
            f"状态：{first_output['status']}；"
            f"任务统计：{first_output['task_summary']}；"
            f"风险摘要：{first_output['risk_summary']}"
        )
