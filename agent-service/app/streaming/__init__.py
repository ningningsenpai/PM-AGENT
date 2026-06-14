"""streaming 模块 —— SSE 流式输出工具。

提供与业务无关的 SSE 事件类型和格式化能力。
"""

from app.streaming.events import StreamEventType
from app.streaming.sse import SSEFormatter

__all__ = ["StreamEventType", "SSEFormatter"]
