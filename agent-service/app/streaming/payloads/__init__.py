"""streaming.payloads 模块 —— Agent 接入层请求 / 响应数据结构。"""

from app.streaming.payloads.request import (
    AgentChatRequest,
    ChatMessage,
    ConversationContext,
    MessageRole,
    ToolCallRef,
    UserContext,
)
from app.streaming.payloads.validators import (
    check_all,
    check_last_is_user,
    check_first_is_system,
    check_role_specific_fields,
    check_system_position,
    check_tool_call_pairing,
)

__all__ = [
    "AgentChatRequest",
    "ChatMessage",
    "ConversationContext",
    "MessageRole",
    "ToolCallRef",
    "UserContext",
    "check_all",
    "check_last_is_user",
    "check_first_is_system",
    "check_role_specific_fields",
    "check_system_position",
    "check_tool_call_pairing",
]
