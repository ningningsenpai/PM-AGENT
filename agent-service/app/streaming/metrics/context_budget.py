from pydantic import BaseModel, Field


class ContextLengthStatus(BaseModel):
    """最近一次上下文长度检查结果。"""

    available: bool = Field(..., description="是否具备可判断的 usage 与上下文窗口配置")
    used_tokens: int | None = Field(default=None, description="最近一次请求实际使用的输入 token")
    max_context_tokens: int | None = Field(default=None, description="模型允许的最大上下文窗口")
    reserved_output_tokens: int = Field(default=0, description="预留给输出的 token 数")
    remaining_tokens: int | None = Field(default=None, description="预留输出后剩余可用 token")
    exceeded: bool | None = Field(default=None, description="是否超过最大上下文窗口")
    near_limit: bool | None = Field(default=None, description="是否接近最大上下文窗口")
