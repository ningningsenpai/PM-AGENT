"""Agent 接入层响应数据结构。"""

from pydantic import BaseModel, Field

from app.streaming.metrics import LLMTokenUsage


class ToolCallRecord(BaseModel):
    """工具调用记录。"""

    call_id: str = Field(default="", description="模型生成的工具调用 ID")
    tool_name: str = Field(..., description="工具名称")
    input: dict = Field(default_factory=dict, description="工具入参")
    output: dict = Field(default_factory=dict, description="工具出参")
    status: str = Field(default="success", description="工具调用状态")
    summary: str = Field(default="", description="面向用户的安全结果摘要")
    error_code: str | None = Field(default=None, description="稳定错误标识")
    error_message: str | None = Field(default=None, description="安全错误信息")
    duration_ms: int = Field(default=0, ge=0, description="执行耗时")


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


class ToolCallPayload(BaseModel):
    """SSE 工具调用开始事件。"""

    callId: str
    toolName: str
    arguments: dict | None = None
    step: int = Field(ge=1)


class ToolResultPayload(BaseModel):
    """SSE 工具调用完成事件，不暴露完整业务结果。"""

    callId: str
    toolName: str
    status: str
    summary: str
    errorCode: str | None = None
    durationMs: int = Field(ge=0)
    step: int = Field(ge=1)


class StreamErrorPayload(BaseModel):
    """流式响应启动后的统一错误事件。"""

    code: int
    message: str
    traceId: str
