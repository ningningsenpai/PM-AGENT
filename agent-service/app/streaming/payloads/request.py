from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
    """用户身份 —— 确认"谁在说话"。"""

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

    @model_validator(mode="after")
    def _check_messages(self) -> "AgentChatRequest":
        """校验 messages 满足多轮对话基本约束。"""
        # 最后一条必须是 user，否则模型没有可回答的输入。
        if self.messages[-1].role != "user":
            raise ValueError("需要用户输入才能继续对话")
        # system 消息(模型定位信息)只允许出现在最前面，防止前端伪造 system 信息越权攻击
        # TODO 需要完善 build_chat_message 函数，确保迭代次数更新之后 system 消息依旧位于最上层
        for index, message in enumerate(self.messages):
            if message.role == "system" and index != 0:
                raise ValueError("system 消息只能出现在 messages 列表第一条")
        return self

    def last_user_message(self) -> str:
        """返回最后一条 user 消息的文本内容，便于工具触发判断。"""
        return self.messages[-1].content
