from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(..., min_length=1, description="用户输入")
    project_id: int | None = Field(default=None, description="项目 ID，可为空")
    stream: bool = Field(default=False, description="是否使用流式输出")
    use_tool_demo: bool = Field(default=False, description="是否强制演示工具调用")


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
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class ApiResponse(BaseModel):
    """统一响应结构。"""

    code: int = 0
    message: str = "成功"
    data: ChatResponse | None = None
    traceId: str
