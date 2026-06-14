"""消息序列校验工具。

把 ``AgentChatRequest`` 的请求级校验从模型内部抽出来，做成一组无状态、
入参只依赖 ``list[ChatMessage]`` 的纯函数，便于：

- 多处复用：请求入口、Agent 迭代追加消息后、Trace 回放等场景都能直接调用；
- 独立单测：构造一段 messages 即可覆盖，无需构造完整请求体；
- 顺序清晰：所有规则的执行顺序在 :func:`check_all` 中单点声明。

校验失败统一抛 :class:`ValueError`，由上层 Pydantic / FastAPI 转成 422 响应。
"""

from app.streaming.payloads.request import ChatMessage


def check_last_is_user(messages: list[ChatMessage]) -> None:
    """最后一条必须是 user，否则模型没有可回答的输入。"""
    if messages[-1].role != "user":
        raise ValueError("需要用户输入才能继续对话")

def check_role_specific_fields(message : ChatMessage) -> None:
    """根据角色校验扩展字段是否合规。"""
    if message.role == "tool" and not message.tool_call_id:
        raise ValueError("tool 角色的消息必须携带 tool_call_id")
    if message.role != "assistant" and message.tool_calls:
        raise ValueError("tool_calls 只能出现在 assistant 消息上")
    if message.role != "tool" and message.tool_call_id:
        raise ValueError("tool_call_id 只能出现在 tool 消息上")


def check_system_position(messages: list[ChatMessage]) -> None:
    """system 消息只能出现在 messages 列表第一条。

    限制 system 位置可以防止前端伪造 system 消息越权篡改模型人设；
    服务端会在 Prompt 构造时统一重建 system，因此首位以外的 system 一律拒绝。
    """
    for index, message in enumerate(messages):
        if message.role == "system" and index != 0:
            raise ValueError(
                f"system 消息只能出现在 messages 列表第一条；当前位于第 {index} 条"
            )


def check_tool_call_pairing(messages: list[ChatMessage]) -> None:
    """校验 ``assistant.tool_calls`` 与 ``tool`` 消息严格成对。

    协议硬约束（OpenAI / DeepSeek 等兼容协议）：

    1. assistant 触发的每个 ``tool_calls[*].id`` 都必须在后续 messages 中找到
       同 ``tool_call_id`` 的 tool 消息；
    2. 每个 tool 消息的 ``tool_call_id`` 都必须能在前面 assistant 的
       ``tool_calls`` 列表中找到来源；
    3. tool 消息必须紧跟触发它的 assistant，中间不能插 user / system；
    4. user 消息出现时，上一轮 assistant 的所有 tool 调用必须已经全部响应。

    任一违反都会被 LLM API 直接拒绝（400），因此提前在入口层拦截，
    避免空跑 LLM 浪费 token。
    """
    # 待响应的 tool_call_id → 触发它的 assistant 在 messages 中的下标。
    pending: dict[str, int] = {}
    # 已经成功配对过的 id，用来检测重复 ID（前端伪造 / 客户端 bug）。
    seen: set[str] = set()

    for idx, msg in enumerate(messages):
        if msg.role == "assistant" and msg.tool_calls:
            # 触发方入队：登记本条 assistant 上的所有 tool_call id。
            for call in msg.tool_calls:
                if not call.id:
                    raise ValueError(f"第 {idx} 条 assistant.tool_calls 缺少 id")
                if call.id in pending or call.id in seen:
                    raise ValueError(f"tool_call_id 重复：{call.id}")
                pending[call.id] = idx

        elif msg.role == "tool":
            # 响应方出队：必须能在 pending 中找到对应 id。
            tid = msg.tool_call_id
            if not tid:
                # ChatMessage 自带校验，这里防御性兜底。
                raise ValueError(f"第 {idx} 条 tool 消息缺少 tool_call_id")
            if tid not in pending:
                raise ValueError(
                    f"第 {idx} 条 tool 消息的 tool_call_id={tid} "
                    f"找不到对应的 assistant.tool_calls"
                )
            # 顺序约束：tool 与触发它的 assistant 之间不允许插 user / system。
            trigger_idx = pending[tid]
            for between in messages[trigger_idx + 1: idx]:
                if between.role in ("user", "system"):
                    raise ValueError(
                        f"tool_call_id={tid} 与触发它的 assistant(第 {trigger_idx} 条) "
                        f"之间被 {between.role} 消息打断"
                    )
            pending.pop(tid)
            seen.add(tid)

        elif msg.role == "user":
            # user 出现 = 新一轮开始；此刻上一轮 tool 链必须已经闭合。
            if pending:
                raise ValueError(
                    f"上一轮 assistant.tool_calls 未全部响应即出现新的 user 消息："
                    f"未响应的 tool_call_id={list(pending.keys())}"
                )

    # 遍历结束：仍有未响应的 tool_calls 视为漏发 tool 响应。
    # 在当前协议下 messages 最后一条必为 user（已由 check_last_is_user 保证），
    # 此分支属于兜底，未来协议放宽时仍能拦住回归。
    if pending:
        raise ValueError(
            f"存在未响应的 tool_calls：{list(pending.keys())}"
        )


def check_all(messages: list[ChatMessage]) -> None:
    """按规定顺序串联所有校验规则；新增规则统一在这里追加。

    规则之间存在短路依赖：``check_last_is_user`` 失败时其余规则没有意义，
    因此先检查它；其它规则之间相互独立。
    """
    check_last_is_user(messages)
    check_system_position(messages)
    check_tool_call_pairing(messages)
