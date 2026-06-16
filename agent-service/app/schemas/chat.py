"""Agent 对话响应数据结构。

响应结构已迁移到 app/streaming/payloads/response.py。
"""

from app.streaming.payloads.response import ApiResponse, ChatResponse, ToolCallRecord

__all__ = ["ApiResponse", "ChatResponse", "ToolCallRecord"]
