"""SSE 流式输出事件类型定义。

与业务代码分离，后续新增事件类型只需在此扩展。
"""
from enum import Enum


class StreamEventType(str, Enum):
    """SSE 流式输出事件类型。

    前端根据 event 字段做不同渲染：
    - meta：连接确认，展示模型和会话信息
    - tool_call：工具开始调用，展示工具名称和入参
    - tool_result：工具调用完成，展示工具返回结果
    - token：模型逐字输出，追加到对话气泡
    - error：发生错误，展示错误信息
    - done：流结束，关闭连接或展示用量摘要
    """

    META = "meta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN = "token"
    ERROR = "error"
    DONE = "done"
