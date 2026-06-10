from collections.abc import AsyncIterator

from app.core.config import Settings
from app.llm.deepseek_client import DeepSeekClient
from app.prompts.project_chat import build_project_chat_prompt
from app.schemas.chat import ChatRequest, ChatResponse, ToolCallRecord
from app.tools.demo_project_tool import DemoProjectTool


class ProjectChatAgent:
    """第 3 阶段项目问答 Agent Demo。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = DeepSeekClient(settings)
        self.project_tool = DemoProjectTool()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        tool_calls = self._maybe_call_tools(request)
        prompt = build_project_chat_prompt(request.message, self._tool_summary(tool_calls))
        answer = await self.llm.chat(prompt)
        return ChatResponse(
            answer=answer,
            model=self.settings.deepseek_model,
            demo_mode=self.settings.demo_mode,
            tool_calls=tool_calls,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[dict]:
        tool_calls = self._maybe_call_tools(request)
        for tool_call in tool_calls:
            yield {"event": "tool_call", "data": tool_call.model_dump()}

        prompt = build_project_chat_prompt(request.message, self._tool_summary(tool_calls))
        async for token in self.llm.stream_chat(prompt):
            yield {"event": "token", "data": token}
        yield {
            "event": "done",
            "data": {
                "model": self.settings.deepseek_model,
                "demo_mode": self.settings.demo_mode,
            },
        }

    def _maybe_call_tools(self, request: ChatRequest) -> list[ToolCallRecord]:
        if request.use_tool_demo or "项目" in request.message or "任务" in request.message:
            return [self.project_tool.run(request.project_id)]
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
