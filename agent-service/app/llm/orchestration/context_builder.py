"""LLM 上下文构造器。"""

from __future__ import annotations

from app.llm.orchestration.compression import compress_old_messages
from app.llm.prompts.project_chat import ensure_system_prompt
from app.streaming.payloads import AgentChatRequest, ChatMessage, check_all

__all__ = ["LLMContextBuilder"]


class LLMContextBuilder:
    """LLMContextBuilder 负责重建 system prompt 并按 token 预算压缩历史。"""

    def __init__(
        self,
        request: AgentChatRequest,
        *,
        max_context_tokens: int | None = None,
        reserved_output_tokens: int = 0,
    ) -> None:
        self.request = request
        self.messages = request.messages
        self.max_context_tokens = max_context_tokens
        self.reserved_output_tokens = reserved_output_tokens

    def build(self) -> list[ChatMessage]:
        """构造标准化后的 LLM 输入消息。"""
        messages = ensure_system_prompt(self.messages)
        check_all(messages)
        if self._should_compress():
            messages = compress_old_messages(messages)
            check_all(messages)
        return messages

    def _should_compress(self) -> bool:
        """仅估算本次消息，不用前端提交的累计 usage 作为输入长度。"""
        from app.llm.telemetry import input_upper_bound

        if self.max_context_tokens is None:
            return False
        actual = input_upper_bound(
            {"messages": [message.model_dump(mode="json") for message in self.messages]}
        )
        return actual + self.reserved_output_tokens > self.max_context_tokens
