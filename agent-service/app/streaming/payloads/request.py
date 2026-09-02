from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.identifiers import SnowflakeId
from app.streaming.metrics import ContextLengthStatus

# TODO 对话持久化模块完成后重新审查该模块数据结构字段的默认值

# 允许的消息角色，对齐 OpenAI 协议。
MessageRole = Literal["system", "user", "assistant", "tool"]


class ToolCallRef(BaseModel):
    """assistant 消息中触发的工具调用引用。"""

    id: str = Field(..., description="工具调用 ID，用于与 tool 角色消息关联")
    name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="工具入参，JSON 对象",
    )


class ChatMessage(BaseModel):
    """单轮对话消息。用于承担 user 提出的需求或者 assistant 回复。"""

    role: MessageRole = Field(..., description="角色：system / user / assistant / tool / memory")
    content: str = Field(default="", description="消息内容；assistant 调用工具时可为空")
    name: str | None = Field(default=None, description="可选名称，用于区分多用户或多工具")
    tool_calls: list[ToolCallRef] | None = Field(
        default=None,
        description="assistant 触发的工具调用列表",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="tool 消息关联的工具调用 ID, 用于保证 assistant 调用的 tool_call_id 与 tool 消息的 tool_call_id 一致",
    )

    @model_validator(mode="after")
    def _check_role_specific_fields(self) -> "ChatMessage":
        """根据角色校验扩展字段是否合规。"""
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("tool 角色的消息必须携带 tool_call_id")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("tool_calls 只能出现在 assistant 消息上")
        if self.role != "tool" and self.tool_call_id:
            raise ValueError("tool_call_id 只能出现在 tool 消息上")
        return self


class ConversationContext(BaseModel):
    """对话业务上下文"""

    project_id: SnowflakeId = Field(..., description="当前项目 ID")
    iteration_id: int = Field(..., description="当前迭代 ID, 用于区分多轮对话")
    context_total_usage: int = Field(
        ...,
        description="当前迭代ID轮次对应的总token消耗数量，用于统计上下文长度从而进行上下文压缩或者切分"
    )
    task_id: int = Field(..., description="当前任务 ID")


class UserContext(BaseModel):
    """用户身份。"""

    user_id: SnowflakeId = Field(..., description="用户 ID")
    user_name: str = Field(..., description="用户显示名称")


class AgentChatRequest(BaseModel):
    """Agent 对话请求 —— 前端传递的完整数据结构。"""

    trace_id: str = Field(..., description="前端传入的链路追踪 ID")
    conversation_id: int = Field(
        ...,
        description="会话 ID；前端传递已有 ID，或者由 Python 业务模块生成"
    )
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description="对话消息列表；包含历史，最后一条为当前轮 user 消息",
    )
    context: ConversationContext = Field(
        default_factory=ConversationContext,
        description="对话业务上下文",
    )
    user: UserContext = Field(
        default_factory=UserContext,
        description="用户身份",
    )
    llm_provider: str | None = Field(
        default=None,
        description="本次请求使用的模型提供方；留空则使用服务端默认。"
                    "当前可选：deepseek / doubao",
    )
    @model_validator(mode="after")
    def _check_messages(self) -> "AgentChatRequest":
        """串联所有消息序列规则；规则实现集中在 validators 模块。"""
        # 延迟导入避免与 ChatMessage 形成循环依赖
        from app.streaming.payloads.validators import check_all

        check_all(self.messages)
        if any(
            message.role == "tool" or message.tool_calls
            for message in self.messages
        ):
            raise ValueError("客户端不得提交工具调用或工具结果消息")
        return self

    def current_round_index(self) -> int:
        """按 user 消息数量计算当前会话轮次。"""
        return sum(1 for message in self.messages if message.role == "user")

    def check_context_length(
        self,
        *,
        max_context_tokens: int | None,
        reserved_output_tokens: int = 0,
        warning_ratio: float = 0.8,
        provider: str | None = None,
    ) -> ContextLengthStatus:
        """基于请求携带的上下文累计 token 判断是否需要压缩。"""
        used_tokens = self.context.context_total_usage
        if max_context_tokens is None:
            return ContextLengthStatus(
                available=False,
                used_tokens=used_tokens,
                max_context_tokens=max_context_tokens,
                reserved_output_tokens=reserved_output_tokens,
            )

        required_tokens = used_tokens + reserved_output_tokens
        remaining_tokens = max_context_tokens - required_tokens
        return ContextLengthStatus(
            available=True,
            used_tokens=used_tokens,
            max_context_tokens=max_context_tokens,
            reserved_output_tokens=reserved_output_tokens,
            remaining_tokens=remaining_tokens,
            exceeded=required_tokens > max_context_tokens,
            near_limit=required_tokens >= int(max_context_tokens * warning_ratio),
        )
