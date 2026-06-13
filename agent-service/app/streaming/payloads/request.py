from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.streaming.metrics import ContextLengthStatus, LLMTokenUsage

# TODO 完善 Java 模块之后重新审查设计该模块数据结构字段的 default 值

# 允许的消息角色，对齐 OpenAI 协议。
MessageRole = Literal["system", "user", "assistant", "tool"]


class ToolCallRef(BaseModel):
    """assistant 消息中触发的工具调用引用。"""

    id: str = Field(..., description="工具调用 ID，用于与 tool 角色消息关联")
    name: str = Field(..., description="工具名称")
    arguments: dict = Field(default_factory=dict, description="工具入参，JSON 对象")


class ChatMessage(BaseModel):
    """单轮对话消息。用于承担 user 提出的需求或者 assistant 回复。"""

    role: MessageRole = Field(..., description="角色：system / user / assistant / tool")
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
    confire: bool = Field(
        default=False,
        description="输入判断验证参数，避免多次验证"
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

    project_id: int | None = Field(default=None, description="当前项目 ID")
    iteration_id: int | None = Field(default=None, description="当前迭代 ID, 用于区分多轮对话(拆分任务在Java模块中设计算法实现)")
    task_id: int | None = Field(default=None, description="当前任务 ID")


class UserContext(BaseModel):
    """用户身份 —— 确认\"谁在说话\"。"""

    user_id: str = Field(default="0", description="用户 ID")
    tenant_id: str = Field(default="0", description="租户 ID, 预留字段")
    user_name: str | None = Field(default=None, description="用户显示名称")


class AgentChatRequest(BaseModel):
    """Agent 对话请求 —— 前端传递的完整数据结构。"""

    conversation_id: str | None = Field(
        ...,
        description="会话 ID；前端传递已有ID，或者在Java模块落库时生成"
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
    stream: bool = Field(default=False, description="是否流式输出")
    use_tool_demo: bool = Field(default=False, description="是否强制演示工具调用")
    llm_provider: str | None = Field(
        default=None,
        description="本次请求使用的模型提供方；留空则使用服务端默认。"
                    "当前可选：deepseek / doubao / glm / kimi / minimax",
    )
    token_usage_records: list[LLMTokenUsage] = Field(
        default_factory=list,
        description="本会话已知的每轮 LLM token 用量；当前仅 DeepSeek 有真实统计",
    )

    @model_validator(mode="after")
    def _check_messages(self) -> "AgentChatRequest":
        """串联所有消息序列规则；规则实现集中在 validators 模块。"""
        # 延迟导入避免与 ChatMessage 形成循环依赖
        from app.streaming.payloads.validators import check_all

        check_all(self.messages)
        return self

    def last_user_message(self) -> str:
        """返回最后一条 user 消息的文本内容，便于工具触发判断。"""
        return self.messages[-1].content

    def current_round_index(self) -> int:
        """按 user 消息数量计算当前会话轮次。"""
        return sum(1 for message in self.messages if message.role == "user")

    def record_token_usage(self, usage: LLMTokenUsage | None) -> LLMTokenUsage | None:
        """记录本轮 token 用量；usage 为空时不处理。"""
        if usage is None:
            return None
        usage = usage.model_copy(
            update={"round_index": usage.round_index or self.current_round_index()}
        )
        self.token_usage_records.append(usage)
        return usage

    def latest_token_usage(self, provider: str | None = None) -> LLMTokenUsage | None:
        """返回最近一条已知 token 用量；provider 不为空时仅匹配指定提供方。"""
        for usage in reversed(self.token_usage_records):
            if provider is None or usage.provider == provider:
                return usage
        return None

    def check_context_length(
        self,
        *,
        max_context_tokens: int | None,
        reserved_output_tokens: int = 0,
        warning_ratio: float = 0.8,
        provider: str | None = None,
    ) -> ContextLengthStatus:
        """基于最近一次真实 usage 判断上下文长度状态。

        该方法使用 provider 返回的 prompt_tokens，因此只能判断最近一次实际调用
        是否接近或超过模型上下文窗口，不等同于调用前 tokenizer 预估。
        """
        usage = self.latest_token_usage(provider)
        if usage is None or usage.input_tokens is None or max_context_tokens is None:
            return ContextLengthStatus(
                available=False,
                used_tokens=usage.input_tokens if usage else None,
                max_context_tokens=max_context_tokens,
                reserved_output_tokens=reserved_output_tokens,
            )

        used_tokens = usage.input_tokens
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
