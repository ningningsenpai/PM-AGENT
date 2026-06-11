# Agent Service

`agent-service` 是 PM-Agent 的 Python Agent 对话服务。当前版本已去除对 Java 模块的运行依赖，可单独启动、单独测试，实现 FastAPI 接口、Agent 编排、Prompt 构造、模型适配和工具调用的完整链路。

---

## 1. 当前定位

当前服务只做一件事：

```text
接收用户问题 → 可选调用工具 → 构造 Prompt → 调用模型 → 返回 JSON / SSE
```

核心边界：

1. 不连接 MySQL；
2. 不依赖 Java 后端；
3. 不真实修改项目、任务、用户等业务数据；
4. 必须配置 `DEEPSEEK_API_KEY` 才能启动，否则报错退出；
5. 内置工具当前返回固定演示数据，等待替换为真实工具 API。

---

## 2. 目录结构与分层职责

```text
agent-service/
├── pyproject.toml                  # 项目元信息与依赖声明（FastAPI、httpx、Pydantic 等）
├── .env.example                    # 环境变量模板（模型 Key、模型名、服务端口）
└── app/
    ├── main.py                     # 应用入口：创建 FastAPI 实例，组装路由
    ├── api/
    │   └── v1/
    │       └── agent.py            # HTTP 接口层：接收请求，解析参数，决定 JSON/SSE 输出
    ├── core/
    │   └── config.py               # 配置层：加载 .env，提供 Settings 实例
    ├── agents/
    │   └── project_chat_agent.py   # Agent 编排层：串联工具调用 → Prompt 构造 → 模型调用
    ├── prompts/
    │   └── project_chat.py         # Prompt 层：定义系统提示与 messages 组装策略
    ├── llm/
    │   └── deepseek_client.py      # LLM 适配层：封装 DeepSeek API 的 Chat Completions 调用
    ├── tools/
    │   └── demo_project_tool.py    # 工具层：提供可被 Agent 调用的业务工具（当前为演示数据）
    └── schemas/
        └── chat.py                 # 数据模型层：定义请求/响应 Pydantic 模型
```

### 各层角色

| 层 | 文件 | 角色 |
|-----|------|------|
| 入口 | `main.py` | 创建 FastAPI 实例，注册路由 |
| 接口层 | `api/v1/agent.py` | 解析 HTTP 请求，调度 Agent，控制响应格式 |
| 配置层 | `core/config.py` | 从 `.env` 读取运行配置，校验 API Key |
| 编排层 | `agents/project_chat_agent.py` | 协调工具调用、Prompt、模型三者的执行顺序 |
| Prompt 层 | `prompts/project_chat.py` | 定义系统角色、边界约束，拼接上下文 |
| LLM 层 | `llm/deepseek_client.py` | 封装模型 API 调用，支持流式与非流式 |
| 工具层 | `tools/demo_project_tool.py` | 提供工具定义与执行逻辑，返回结构化数据 |
| Schema 层 | `schemas/chat.py` | 定义请求体和响应体的数据结构 |

---

## 3. 已包含功能与接口

### 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/internal/health` | 健康检查，返回服务状态 |
| `POST` | `/api/v1/agent/chat` | Agent 对话，支持 JSON 和 SSE 流式两种输出 |

### 功能

| 能力 | 说明 |
|---|---|
| 非流式对话 | `POST /api/v1/agent/chat`，`stream=false`，返回完整 JSON |
| SSE 流式对话 | `POST /api/v1/agent/chat`，`stream=true`，逐 token 推送 |
| DeepSeek 模型适配 | 默认模型 `deepseek-v4-pro`，通过 `.env` 配置 Key 和 Base URL |
| 工具调用演示 | `demo_query_project_overview` 返回固定项目概览数据 |