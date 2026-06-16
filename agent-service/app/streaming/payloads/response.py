"""Agent 接入层响应数据结构。"""

from pydantic import BaseModel, Field

from app.streaming.metrics import LLMTokenUsage


class ToolCallRecord(BaseModel):
    """工具调用记录。"""

    tool_name: str = Field(..., description="工具名称")
    input: dict = Field(default_factory=dict, description="工具入参")
    output: dict = Field(default_factory=dict, description="工具出参")
    status: str = Field(default="success", description="工具调用状态")


class ChatResponse(BaseModel):
    """Agent 非流式对话响应。"""

    answer: str = Field(..., description="Agent 回答内容")
    model: str = Field(..., description="实际调用的模型名称")
    conversation_id: int = Field(..., description="会话 ID")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, description="工具调用记录")
    usage: LLMTokenUsage | None = Field(default=None, description="本轮 LLM token 用量")


class ApiResponse(BaseModel):
    """统一 JSON 响应结构。"""

    code: int = Field(default=0, description="业务错误码，0 表示成功")
    message: str = Field(default="成功", description="响应消息")
    data: ChatResponse | None = Field(default=None, description="响应数据")
    traceId: str = Field(..., description="链路追踪 ID")


class StreamMetaPayload(BaseModel):
    """SSE meta 事件数据。"""

    traceId: str = Field(..., description="链路追踪 ID")
    conversationId: int = Field(..., description="会话 ID")
    userId: int = Field(..., description="用户 ID")
    tenantId: int = Field(..., description="租户 ID")


class StreamDonePayload(BaseModel):
    """SSE done 事件数据。"""

    model: str = Field(..., description="实际调用的模型名称")
    provider: str = Field(..., description="模型提供方")
    conversationId: int = Field(..., description="会话 ID")
    usage: LLMTokenUsage | None = Field(default=None, description="本轮 LLM token 用量")
