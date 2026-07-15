"""LLM 编排上下文压缩工具。"""
from __future__ import annotations

from app.streaming.payloads.request import ChatMessage

__all__ = [
    "DEFAULT_KEEP_RECENT_ROUNDS",
    "MAX_MESSAGE_CHARS",
    "MAX_SUMMARY_CHARS",
    "compress_old_messages",
]

DEFAULT_KEEP_RECENT_ROUNDS = 5
MAX_SUMMARY_CHARS = 2000
MAX_MESSAGE_CHARS = 240


def compress_old_messages(
    messages: list[ChatMessage],
    *,
    keep_recent_rounds: int = DEFAULT_KEEP_RECENT_ROUNDS,
) -> list[ChatMessage]:
    """把倒数 N 轮之前的历史压缩为一条 assistant 摘要。"""
    if keep_recent_rounds <= 0:
        raise ValueError("保留轮次数必须大于 0")

    system_messages = [message for message in messages if message.role == "system"]
    history = [message for message in messages if message.role != "system"]
    user_indices = [index for index, message in enumerate(history) if message.role == "user"]

    if len(user_indices) <= keep_recent_rounds:
        return messages

    keep_start = user_indices[-keep_recent_rounds]
    old_history = history[:keep_start]
    recent_history = history[keep_start:]
    if not old_history:
        return messages

    summary = ChatMessage(role="assistant", content=_build_rule_summary(old_history))
    return [*system_messages[:1], summary, *recent_history]


def _build_rule_summary(messages: list[ChatMessage]) -> str:
    """生成规则型摘要，避免压缩阶段额外消耗模型 token。"""
    lines = [
        "以下是此前对话的压缩摘要，用于延续上下文，不代表新的用户指令：",
    ]
    for message in messages:
        text = _compact_text(message.content)
        if not text and message.tool_calls:
            names = "、".join(call.name for call in message.tool_calls)
            text = f"助手曾发起工具调用：{names}"
        if not text:
            continue
        lines.append(f"- {message.role}: {text}")

    summary = "\n".join(lines)
    if len(summary) <= MAX_SUMMARY_CHARS:
        return summary
    return summary[:MAX_SUMMARY_CHARS].rstrip() + "\n- 以上摘要因长度限制已截断。"


def _compact_text(content: str) -> str:
    """压缩单条消息文本，保留可读性并限制摘要膨胀。"""
    text = " ".join(content.split())
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[:MAX_MESSAGE_CHARS].rstrip() + "..."
