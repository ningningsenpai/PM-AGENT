from app.prompts.project_chat import ensure_system_prompt
from app.streaming.payloads import AgentChatRequest, ChatMessage, check_all


class LLMContextBuilder:
    """ LLM 上下文构造器
     主要职责：
        - 完善对话迭代之后 system 提示词位于上下文最上方
        - 迭代之后拼接上一轮上下文压缩后的prompt
    调用链路：
        - 当前轮次迭代 -> Java 模块传递规定上下文长度的 AgentChatRequest
        - 新迭代轮次 -> Java 模块首先调用 上下文压缩算法然后重新组装 prompt 然后返回新的 AgentChatRequest
    """
    def __init__(self, request: AgentChatRequest) -> None:
        self.request = request
        self.messages = request.messages

    def build(self) -> list[ChatMessage]:
        """构造标准化后的 LLM 输入消息。"""
        messages = ensure_system_prompt(self.messages)
        check_all(messages)
        return messages


