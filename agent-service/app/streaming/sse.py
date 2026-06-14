"""SSE 协议格式化工具。

将结构化的流式事件转换为符合 SSE 规范的文本行。
与业务代码分离，所有 SSE 输出均通过此工具格式化。
"""
import json
from pydantic import BaseModel
from app.streaming.events import StreamEventType


class SSEFormatter:
    """SSE 协议格式化工具。

    用法：

        formatter = SSEFormatter()
        line = formatter.format(StreamEventType.META, {"traceId": "abc"})
        # → "event: meta\\ndata: {\"traceId\": \"abc\"}\\n\\n"

        # 流结束时调用
        formatter.done_marker()
        # → "data: [DONE]\\n\\n"
    """

    @staticmethod
    def format(event: StreamEventType, data: dict | str | BaseModel) -> str:
        """将事件类型和数据格式化为 SSE 文本行。

        Args:
            event: 事件类型，见 StreamEventType 枚举
            data: 事件数据，支持 dict、str 或 Pydantic 模型

        Returns:
            SSE 格式文本，末尾已包含双换行
        """
        if isinstance(data, BaseModel):
            payload = data.model_dump_json()
        elif isinstance(data, str):
            payload = data
        else:
            payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event.value}\ndata: {payload}\n\n"

    @staticmethod
    def done_marker() -> str:
        """SSE 流结束标记。

        部分 SSE 客户端以此标记判断流结束。
        """
        return "data: [DONE]\n\n"
