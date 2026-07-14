"""用假模型演示一次完整的原生 tool_calls 循环。"""

from __future__ import annotations

import json
from typing import Any


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_project_overview",
            "description": "查询项目概览和任务统计",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "项目 ID"},
                },
                "required": ["project_id"],
            },
        },
    }
]


def query_project_overview(project_id: int) -> dict[str, Any]:
    """模拟 Java 工具 API 返回的确定性业务数据。"""
    return {
        "project_id": project_id,
        "project_name": "PM-Agent",
        "status": "开发中",
        "task_summary": {"待处理": 2, "进行中": 3, "已完成": 5},
    }


TOOL_REGISTRY = {"query_project_overview": query_project_overview}


def fake_model_chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """模拟支持 tool_calls 的模型；真实场景由 DeepSeek 等模型返回相同结构。"""
    if not tools:
        raise ValueError("必须向模型声明可用工具")

    if messages[-1]["role"] == "tool":
        tool_result = json.loads(messages[-1]["content"])
        summary = tool_result["task_summary"]
        return {
            "role": "assistant",
            "content": (
                f"项目 {tool_result['project_name']} 当前为{tool_result['status']}，"
                f"待处理 {summary['待处理']} 个、进行中 {summary['进行中']} 个、"
                f"已完成 {summary['已完成']} 个任务。"
            ),
        }

    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_001",
                "type": "function",
                "function": {
                    "name": "query_project_overview",
                    "arguments": json.dumps({"project_id": 101}),
                },
            }
        ],
    }


def run_demo() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "项目 101 现在进展怎么样？"},
    ]

    print("1. 第一次调用模型：模型判断需要查询项目数据")
    assistant_message = fake_model_chat(messages, TOOLS)
    print(json.dumps(assistant_message, ensure_ascii=False, indent=2))
    messages.append(assistant_message)

    print("\n2. 编排器收到 tool_calls，校验参数并执行本地工具")
    for tool_call in assistant_message.get("tool_calls", []):
        function = tool_call["function"]
        arguments = json.loads(function["arguments"])
        result = TOOL_REGISTRY[function["name"]](**arguments)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function["name"],
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    print("\n3. 第二次调用模型：模型读取工具结果并生成用户回答")
    final_message = fake_model_chat(messages, TOOLS)
    print(final_message["content"])


if __name__ == "__main__":
    run_demo()
