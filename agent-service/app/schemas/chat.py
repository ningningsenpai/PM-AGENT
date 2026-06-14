"""Agent 对话响应数据结构。

请求结构已迁移到 app/streaming/payloads/request.py 下的 AgentChatRequest，
这里只保留响应与工具调用记录。
"""

from pydantic import BaseModel, Field

from app.streaming.metrics import LLMTokenUsage, LLMTokenUsageSummary


class ToolCallRecord(BaseModel):
    """工具调用记录。"""

    tool_name: str
    input: dict
    output: dict
    status: str = "success"


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    answer: str
    model: str
    conversation_id: str | None = Field(default=None, description="会话 ID")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: LLMTokenUsage | None = Field(default=None, description="本轮 LLM token 用量")
    usage_summary: LLMTokenUsageSummary = Field(
        default_factory=LLMTokenUsageSummary,
        description="当前会话累计 LLM token 用量",
    )


class ApiResponse(BaseModel):
    """统一响应结构。"""

    code: int = 0
    message: str = "成功"
    data: ChatResponse | None = None
    traceId: str
