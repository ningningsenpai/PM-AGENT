from collections.abc import AsyncIterator

from app.core.config import Settings
from app.llm.deepseek_client import DeepSeekClient
from app.prompts.project_chat import build_project_chat_messages
from app.schemas.chat import ChatResponse, ToolCallRecord
from app.streaming import StreamEventType
from app.streaming.payloads import AgentChatRequest
from app.tools.demo_project_tool import DemoProjectTool


class ProjectChatAgent:
    """项目问答 Agent，支持多轮对话。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = DeepSeekClient(settings)
        self.project_tool = DemoProjectTool()

    async def chat(self, request: AgentChatRequest) -> ChatResponse:
        """非流式多轮对话。"""
        tool_calls = self._maybe_call_tools(request)
        messages = build_project_chat_messages(request, self._tool_summary(tool_calls))
        answer = await self.llm.chat(messages)
        return ChatResponse(
            answer=answer,
            model=self.settings.deepseek_model,
            conversation_id=request.conversation_id,
            tool_calls=tool_calls,
        )

    async def stream_chat(self, request: AgentChatRequest) -> AsyncIterator[dict]:
        """流式多轮对话；按事件 yield 工具调用与 token。"""
        tool_calls = self._maybe_call_tools(request)

        for tool_call in tool_calls:
            yield {"event": StreamEventType.TOOL_CALL, "data": tool_call.model_dump()}

        messages = build_project_chat_messages(request, self._tool_summary(tool_calls))
        async for token in self.llm.stream_chat(messages):
            yield {"event": StreamEventType.TOKEN, "data": token}

        yield {
            "event": StreamEventType.DONE,
            "data": {
                "model": self.settings.deepseek_model,
                "conversationId": request.conversation_id,
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
