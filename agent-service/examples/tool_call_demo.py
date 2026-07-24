import asyncio
import json
import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


API_URL = (
    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    + "/chat/completions"
)
API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-1717e02a782945d197e758099ef780ec")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
MAX_TOOL_ROUNDS = 3


# 模拟 system/index.json 中的项目文件条目
DEMO_INDEX = [
    {
        "fileId": 1,
        "logicalPath": "backend/src/main/java/com/ning/pm/auth/AuthController.java",
        "module": "backend-auth",
        "kind": "api",
        "summary": "认证模块 HTTP 接口入口",
        "keywords": ["登录", "注册", "认证"],
    },
    {
        "fileId": 2,
        "logicalPath": "frontend/src/modules/auth/pages/login-page.vue",
        "module": "frontend-auth",
        "kind": "page",
        "summary": "用户登录页面",
        "keywords": ["登录", "表单", "前端"],
    },
    {
        "fileId": 3,
        "logicalPath": "docs/06-Agent设计.md",
        "module": "docs",
        "kind": "document",
        "summary": "Agent 编排、工具调用和 Trace 设计",
        "keywords": ["Agent", "工具调用", "Trace"],
    },
]


class SearchProjectIndexArgs(BaseModel):
    """模型调用项目索引工具时的参数。"""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="需要查询的项目主题")
    limit: int = Field(default=5, ge=1, le=10)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_project_index",
            "description": "查询项目文件索引。回答项目代码、文档和模块问题前应调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要查询的项目主题",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回多少条结果",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["query", "limit"],
                "additionalProperties": False,
            },
        },
    }
]


def search_project_index(arguments: SearchProjectIndexArgs) -> dict[str, Any]:
    """模拟查询 index.json。"""

    query = arguments.query.lower()

    matched = []
    for entry in DEMO_INDEX:
        searchable_text = " ".join(
            [
                entry["logicalPath"],
                entry["module"],
                entry["kind"],
                entry["summary"],
                *entry["keywords"],
            ]
        ).lower()

        if any(word in searchable_text for word in query.split()):
            matched.append(entry)

    return {
        "success": True,
        "query": arguments.query,
        "total": len(matched),
        "items": matched[: arguments.limit],
    }


def execute_tool(tool_call: dict[str, Any]) -> dict[str, Any]:
    """校验并执行模型请求的工具。"""

    function = tool_call.get("function") or {}
    tool_name = function.get("name")
    raw_arguments = function.get("arguments", "{}")

    if tool_name != "search_project_index":
        return {
            "success": False,
            "error": f"不允许调用未注册工具：{tool_name}",
        }

    try:
        arguments = SearchProjectIndexArgs.model_validate_json(raw_arguments)
        return search_project_index(arguments)
    except ValidationError as exception:
        return {
            "success": False,
            "error": "工具参数校验失败",
            "details": exception.errors(include_url=False),
        }


async def call_model(
    client: httpx.AsyncClient,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """调用模型并返回完整 assistant 消息。"""

    response = await client.post(
        API_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "thinking": {"type": "disabled"},
            "temperature": 0.1,
            "stream": False,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]


async def main() -> None:
    if not API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是 PM-Agent。回答项目内部代码和文档问题时，"
                "必须先调用已注册的项目索引工具，不得编造项目事实。"
            ),
        },
        {
            "role": "user",
            "content": "项目里的登录功能涉及哪些文件？",
        },
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        for round_index in range(1, MAX_TOOL_ROUNDS + 1):
            assistant_message = await call_model(client, messages)
            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                print(f"模型最终回答：{assistant_message.get('content', '')}")
                return

            # 必须原样保留 assistant 的 tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                tool_result = execute_tool(tool_call)

                print(
                    f"第 {round_index} 轮工具调用："
                    f"{tool_call['function']['name']} -> {tool_result}"
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

    raise RuntimeError("工具调用轮数超过允许上限")


if __name__ == "__main__":
    asyncio.run(main())