"""项目问答 Prompt 构造。

多轮对话设计要点：
- system 消息固定放在最前面，承载人设与硬约束；
- 业务上下文（项目 / 迭代 / 任务）单独追加一条 system 消息，避免污染 user 历史；
- 历史 messages 原样透传，保持多轮语义；
- 工具调用结果以 system 角色追加在最后一条 user 之前，作为"已知事实"提示模型使用。
"""

from app.streaming.payloads import AgentChatRequest, ChatMessage

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
PM-Agent 是一个基于 Java + Python + 大模型 Agent 构建的智能项目管理平台，面向项目经理、研发团队与管理层，帮助团队自动理解项目状态、识别交付风险、生成项目报告，并推动任务执行。
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
    # TODO 完善项目生成 PROJECT_SYSTEM_PROMPT 的算法
    return PROJECT_SYSTEM_PROMPT


def _context_hint(request: AgentChatRequest) -> str | None:
    """根据业务上下文生成提示文本，没有任何上下文时返回 None。"""
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


def build_project_chat_messages(
    request: AgentChatRequest,
    tool_summary: str | None = None,
    base_messages: list[ChatMessage] | None = None,
) -> list[dict]:
    """构造项目问答的多轮 messages 数组。

    ``base_messages`` 应由 ``LLMContextBuilder.build()`` 产出，包含服务端重建的
    system prompt 与已校验的历史消息；本函数只负责追加业务上下文、工具摘要，
    并转换为 LLM API 可直接接受的 dict 列表。
    """
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

    # 工具摘要作为"已知事实"放在最后一条 user 之前，方便模型立即引用。
    if tool_summary and history and history[-1]["role"] == "user":
        messages.extend(history[:-1])
        messages.append({"role": "system", "content": f"已调用工具得到的项目摘要：{tool_summary}"})
        messages.append(history[-1])
    else:
        messages.extend(history)

    return messages


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
            # DeepSeek / OpenAI 协议中 assistant.tool_calls 是结构化字段，
            # 这里按 OpenAI 风格序列化，便于后续接入真实工具调用。
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                }
                for call in message.tool_calls
            ]
        serialized.append(item)
    return serialized
