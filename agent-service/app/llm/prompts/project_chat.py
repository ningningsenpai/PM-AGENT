"""项目问答 Prompt 构造。"""
from __future__ import annotations

import json

from app.streaming.payloads import AgentChatRequest, ChatMessage

__all__ = [
    "CHAT_SYSTEM_PROMPT",
    "PROJECT_SYSTEM_PROMPT",
    "build_project_chat_messages",
    "ensure_system_prompt",
    "get_project_prompt",
]

CHAT_SYSTEM_PROMPT = """
你是 PM-Agent 的项目管理助手。

必须遵守：
1. 只用中文回答；
2. Python Agent 不直接操作数据库；
3. 如果需要项目、任务等业务数据，只能使用已注册的工具获取业务数据；
4. 信息不足时要说明缺少什么，不要编造项目、任务、人员或日期；
5. 删除、权限变更、对外通知等高风险动作只能生成建议，不能直接执行。
""".strip()

PROJECT_SYSTEM_PROMPT = """
项目定位：
PM-Agent 是一个基于 Vue 3、FastAPI 模块化单体和大模型 Agent 构建的智能项目管理平台，帮助用户理解项目状态、识别交付风险、生成项目报告并推动任务执行。
""".strip()


def ensure_system_prompt(messages: list[ChatMessage]) -> list[ChatMessage]:
    """重建 system prompt，并移除前端传入的 system 消息。"""
    if not messages:
        raise ValueError("messages 不能为空")
    system_message = ChatMessage(
        role="system",
        content=f"{CHAT_SYSTEM_PROMPT}\n\n{get_project_prompt()}",
    )
    history = [message for message in messages if message.role != "system"]
    return [system_message, *history]


def get_project_prompt() -> str:
    """获取项目定位提示词；后续可替换为按项目动态生成。"""
    return PROJECT_SYSTEM_PROMPT


def build_project_chat_messages(
    request: AgentChatRequest,
    tool_summary: str | None = None,
    base_messages: list[ChatMessage] | None = None,
) -> list[dict]:
    """构造项目问答 messages 数组，并注入业务上下文与工具事实。"""
    source_messages = base_messages or request.messages
    history = _serialize_history(source_messages)

    messages: list[dict] = []
    if history and history[0]["role"] == "system":
        messages.append(history[0])
        history = history[1:]
    else:
        messages.append(
            {
                "role": "system",
                "content": f"{CHAT_SYSTEM_PROMPT}\n\n{get_project_prompt()}",
            }
        )

    context_hint = _context_hint(request)
    if context_hint:
        messages.append({"role": "system", "content": context_hint})

    if tool_summary and history and history[-1]["role"] == "user":
        messages.extend(history[:-1])
        messages.append({"role": "system", "content": f"已调用工具得到的项目摘要：{tool_summary}"})
        messages.append(history[-1])
    else:
        messages.extend(history)

    return messages


def _context_hint(request: AgentChatRequest) -> str | None:
    """根据业务上下文生成提示文本。"""
    parts: list[str] = []
    if request.context.project_id is not None:
        parts.append(f"项目 ID={request.context.project_id}")
    if request.context.iteration_id is not None:
        parts.append(f"迭代 ID={request.context.iteration_id}")
    if request.context.task_id is not None:
        parts.append(f"任务 ID={request.context.task_id}")
    if request.user.user_name:
        parts.append(f"提问者={request.user.user_name}")
    if not parts:
        return None
    return "当前对话的业务上下文：" + "；".join(parts)


def _serialize_history(history: list[ChatMessage]) -> list[dict]:
    """把 ChatMessage 列表序列化为 LLM API 可直接接受的 dict 列表。"""
    serialized: list[dict] = []
    for message in history:
        item: dict = {"role": message.role, "content": message.content}
        if message.name:
            item["name"] = message.name
        if message.tool_call_id:
            item["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(
                            call.arguments,
                            ensure_ascii=False,
                        ),
                    },
                }
                for call in message.tool_calls
            ]
        serialized.append(item)
    return serialized
