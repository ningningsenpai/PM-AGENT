# Agent Service

`agent-service` 是 PM-Agent 的 Python Agent 服务，可单独启动和测试，当前提供 Agent 对话与项目文件同步解析能力。

---

## 1. 当前定位

当前服务包含两条独立链路：

```text
接收用户问题 → 可选调用工具 → 构造 Prompt → 调用模型 → 返回 JSON / SSE
接收 Java 受控文件引用 → 下载并校验文件 → 生成文件详情 → 同步返回 JSON
```

核心边界：

1. 不连接 MySQL；
2. 不直接操作 MinIO，文件解析只读取 Java 提供的受控地址；
3. 不真实修改项目、任务、用户等业务数据；
4. 必须配置当前选中 provider 对应的 API Key 才能调用（启动期不强校验，调用期才报错）；
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
    │       ├── agent.py            # Agent 对话接口
    │       └── project_files.py    # 项目文件同步解析接口
    ├── core/
    │   └── config.py               # 配置层：加载 .env，提供 Settings 实例
    ├── agents/
    │   └── project_chat_agent.py   # Agent 编排层：串联工具调用 → Prompt 构造 → 模型调用
    ├── prompts/
    │   └── project_chat.py         # Prompt 层：定义系统提示与 messages 组装策略
    ├── llm/
    │   ├── base.py                 # BaseLLMClient 抽象基类，定义 chat / stream_chat 协议
    │   ├── registry.py             # @register_llm 装饰器与全局注册表
    │   ├── factory.py              # get_llm_client 工厂，按 provider 名解析客户端
    │   ├── context_builder.py      # LLM 上下文构造器（多轮 system 维护、上下文压缩）
    │   └── clients/                # 各厂商客户端实现
    │       ├── openai_compatible.py # OpenAI Chat Completions 兼容客户端基类
    │       ├── deepseek_client.py
    │       └── doubao_client.py
    ├── tools/
    │   └── demo_project_tool.py    # 工具层：提供可被 Agent 调用的业务工具（当前为演示数据）
    ├── project/context/
    │   └── detail_analysis/        # 文件下载、校验、结构解析与可选模型增强
    └── schemas/
        └── chat.py                 # 数据模型层：定义请求/响应 Pydantic 模型
```

### 各层角色

| 层 | 文件 | 角色 |
|-----|------|------|
| 入口 | `main.py` | 创建 FastAPI 实例，注册路由 |
| 接口层 | `api/v1/agent.py` | 解析 HTTP 请求，调度 Agent，控制响应格式 |
| 文件接口层 | `api/v1/project_files.py` | 校验内部令牌并同步返回文件解析结果 |
| 文件解析层 | `project/context/detail_analysis/` | 下载受控文件、校验哈希、生成完整详情 |
| 配置层 | `core/config.py` | 从 `.env` 读取运行配置，校验 API Key |
| 编排层 | `agents/project_chat_agent.py` | 协调工具调用、Prompt、模型三者的执行顺序 |
| Prompt 层 | `prompts/project_chat.py` | 定义系统角色、边界约束，拼接上下文 |
| LLM 层 | `llm/base.py` 等 | 统一 LLM 协议；通过注册表 + 工厂支持运行时切换模型 |
| 工具层 | `tools/demo_project_tool.py` | 提供工具定义与执行逻辑，返回结构化数据 |
| Schema 层 | `schemas/chat.py` | 定义请求体和响应体的数据结构 |

---

## 3. 已包含功能与接口

### 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/internal/health` | 健康检查，返回服务状态 |
| `POST` | `/api/v1/agent/chat` | Agent 对话，支持 JSON 和 SSE 流式两种输出 |
| `POST` | `/api/v1/project-files/analyze` | Java 内部调用的项目文件同步解析接口 |

### 功能

| 能力 | 说明 |
|---|---|
| 非流式对话 | `POST /api/v1/agent/chat`，`stream=false`，返回完整 JSON |
| SSE 流式对话 | `POST /api/v1/agent/chat`，`stream=true`，逐 token 推送 |
| DeepSeek 模型适配 | 默认模型 `deepseek-v4-pro`，通过 `.env` 配置 Key 和 Base URL |
| 多模型切换 | 内置 DeepSeek / 豆包客户端；通过 `DEFAULT_LLM_PROVIDER` 或请求体 `llm_provider` 字段切换 |
| 工具调用演示 | `demo_query_project_overview` 返回固定项目概览数据 |
| 文件同步解析 | 校验内部令牌和文件哈希，直接返回结构化文件详情，不使用 MQ |
