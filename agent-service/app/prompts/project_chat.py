PROJECT_CHAT_SYSTEM_PROMPT = """
你是 PM-Agent 的项目管理助手。

必须遵守：
1. 只用中文回答；
2. Python Agent 不直接操作数据库；
3. 如果需要项目、任务等业务数据，只能使用已注册的工具获取业务数据；
4. 信息不足时要说明缺少什么，不要编造项目、任务、人员或日期；
5. 删除、权限变更、对外通知等高风险动作只能生成建议，不能直接执行。
""".strip()


def build_project_chat_prompt(message: str, tool_summary: str | None = None) -> list[dict[str, str]]:
    """构造项目问答 Prompt。"""
    context = "当前是第 3 阶段 Agent 对话。"
    if tool_summary:
        context += f"\n已调用工具得到的项目摘要：{tool_summary}"
    return [
        {"role": "system", "content": PROJECT_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\n用户问题：{message}"},
    ]
