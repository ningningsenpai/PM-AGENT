# Agent Service

本目录用于存放 PM-Agent 的 Python Agent 服务代码。Python 部分从第 3 阶段开始接入，负责 Agent 编排、Prompt、模型调用、工具选择、流式输出和后续 RAG，不直接操作业务数据库。

---

## 1. 定位

```text
Java 后端 = 业务主系统
Python Agent 服务 = 智能编排服务
```

Python Agent 服务只处理“智能推理和编排”，不承接项目、任务、用户等确定性业务 CRUD。

核心原则：

1. Python 不直接连接 MySQL；
2. Python 不直接修改 `pm_project`、`pm_task` 等业务表；
3. 所有业务查询和业务写入必须通过 Java 工具 API；
4. 高风险动作只生成建议和待确认动作，不静默执行；
5. `traceId` 必须贯穿前端、Java、Python、模型调用和工具调用。

---

## 2. 分级职责规划

### 2.1 第 1 层：API 接入层 `app/api/`

负责接收 Java 后端转发过来的 Agent 请求。

| 子目录 | 职责 |
|---|---|
| `app/api/v1/` | 第 1 版 Agent HTTP API，例如 `/api/v1/agent/chat` |

主要业务：

- 接收 Java 后端传入的用户问题、项目 ID、用户 ID、traceId；
- 返回普通 JSON 响应或流式响应；
- 不做复杂业务判断；
- 不直接调用数据库。

---

### 2.2 第 2 层：核心配置层 `app/core/`

负责应用级基础能力。

| 能力 | 说明 |
|---|---|
| 配置管理 | 读取模型 Key、Java 后端地址、超时时间、开关配置 |
| 日志 | 输出包含 `traceId` 的结构化日志 |
| 错误处理 | 统一 Agent 服务异常结构 |
| 安全边界 | 校验 Java 传入的必要头信息，如 `X-Trace-Id`、`X-User-Id` |

不负责业务 CRUD，也不放具体 Agent 逻辑。

---

### 2.3 第 3 层：Java 客户端层 `app/clients/`

负责调用 Java 后端提供的受控工具 API。

典型职责：

- 统一封装 Java API 基础地址；
- 自动透传：
  - `X-Trace-Id`
  - `X-User-Id`
  - `X-Tenant-Id`
  - 写操作的 `X-Idempotency-Key`
- 处理 Java 返回的统一响应结构；
- 将 Java 业务错误转换成 Agent 可理解的工具错误。

示例工具调用：

```text
GET  /api/v1/tools/projects/{id}/overview
GET  /api/v1/tools/tasks?projectId=xxx
GET  /api/v1/tools/tasks/overdue?projectId=xxx
POST /api/v1/tools/reports/weekly-draft
```

> 当前 Java 工具 API 还未正式实现，本层先预留位置。

---

### 2.4 第 4 层：模型适配层 `app/llm/`

负责统一模型调用。

| 能力 | 说明 |
|---|---|
| 模型请求封装 | 统一 messages、temperature、max_tokens、stream 等参数 |
| 模型响应封装 | 统一 content、usage、finish_reason、error |
| 流式输出 | 把模型 token 流转换为 Agent 事件流 |
| 成本统计 | 记录 token、耗时、模型名、供应商 |
| 模型路由 | 默认 DeepSeek，复杂场景后续升级 Claude / GPT |

第一版默认模型策略：

```text
默认：DeepSeek
复杂推理：后续可升级 Claude / GPT
RAG：第 6 阶段再细化
```

---

### 2.5 第 5 层：Agent 编排层 `app/agents/`

负责具体 Agent 能力的编排，是 Python 服务的核心业务层。

规划能力：

| 阶段 | Agent 能力 | 说明 |
|---|---|---|
| 第 3 阶段 | 项目问答 Agent | 回答用户关于项目状态、任务进展的问题 |
| 第 4 阶段 | 需求拆解 Agent | 将需求草稿拆成任务建议，需要人工确认 |
| 第 4 阶段 | 周报生成 Agent | 基于项目和任务数据生成周报草稿 |
| 第 5 阶段 | 风险分析 Agent | 基于规则结果和项目数据生成风险说明与建议 |
| 第 6 阶段 | RAG 知识问答 Agent | 基于项目文档、会议纪要和历史经验回答问题 |

Agent 编排层负责：

- 判断是否需要调用工具；
- 组织 Prompt；
- 调用模型；
- 校验结构化输出；
- 生成自然语言答复；
- 标记是否需要人工确认。

---

### 2.6 第 6 层：Prompt 模板层 `app/prompts/`

负责维护 Prompt 模板。

模板要求：

1. 每个 Prompt 必须有稳定名称，例如 `project_chat_v1`；
2. Prompt 必须包含业务边界，明确 Python 不直接操作数据库；
3. 信息不足时必须追问；
4. 输出给用户必须是中文；
5. 涉及业务结构化结果时必须声明 JSON 格式。

典型 Prompt 结构：

```text
角色与目标
项目上下文摘要
可用工具清单
业务约束与禁止事项
输出格式要求
用户输入
```

---

### 2.7 第 7 层：工具层 `app/tools/`

负责把 Java 工具 API 封装成 Agent 可调用的工具。

工具需要声明：

| 字段 | 说明 |
|---|---|
| `tool_name` | 工具名，例如 `query_task_list` |
| `description` | 工具用途 |
| `input_schema` | 输入结构 |
| `output_schema` | 输出结构 |
| `permission` | 需要的业务权限 |
| `write_operation` | 是否写业务 |
| `requires_confirmation` | 是否需要人工确认 |

第一批规划工具：

```text
query_project_overview      查询项目概览
query_task_list             查询任务列表
query_overdue_tasks         查询延期任务
query_member_workload       查询成员负载
split_requirement_into_tasks 拆解需求为任务草稿
generate_weekly_report      生成周报草稿
create_risk_candidate       创建风险候选
search_knowledge            检索知识库，第 6 阶段
```

---

### 2.8 第 8 层：Schema 层 `app/schemas/`

负责 Pydantic 数据模型。

主要用途：

- API 请求 / 响应模型；
- 模型结构化输出校验；
- 工具入参 / 出参校验；
- Agent 内部事件模型；
- 流式输出事件模型。

原则：

- 关键业务结果必须结构化；
- 结构化结果必须可校验；
- 校验失败时不能伪造成功，必须返回可追踪错误。

---

### 2.9 第 9 层：RAG 层 `app/rag/`

RAG 第 6 阶段再正式实现。

当前只预留目录，不提前接入向量库。

未来职责：

| 能力 | 说明 |
|---|---|
| 文档解析 | 解析 PDF、Word、Markdown、会议纪要 |
| 文档切片 | 生成可检索 chunk |
| 向量化 | 调用 embedding 模型 |
| 向量检索 | 使用 Qdrant 或 pgvector |
| 引用来源 | 回答时展示文档来源 |

当前阶段不做：

```text
不引入 Qdrant
不引入 pgvector
不实现完整 RAG 链路
```

---

## 3. 与 Java 后端的对接方式

### 3.1 第 3 阶段：同步 HTTP / SSE

用于用户正在等待结果的场景：

```text
前端 → Java 后端 → Python Agent 服务 → LLM
                  ↘ Python 调 Java 工具 API
```

典型流程：

```text
1. 前端调用 Java：POST /api/v1/agent/chat
2. Java 校验登录态、项目权限、traceId
3. Java 调用 Python：POST /api/v1/agent/chat
4. Python 组织 Prompt 并调用模型
5. Python 如需业务数据，通过 Java 工具 API 查询
6. Python 返回流式事件或最终回答
7. Java 转发给前端，并协作记录 Trace
```

---

### 3.2 第 5 阶段：异步 MQ

用于长耗时任务：

```text
Java 发布任务 → RabbitMQ → Python 消费任务 → 模型 / 工具 / RAG → Java 查询结果
```

适合：

- 每日风险扫描；
- 批量周报生成；
- 文档解析与向量化；
- 大批量 Agent 任务。

---

## 4. 推荐目录结构

```text
agent-service/
├── README.md
├── pyproject.toml              # 后续正式编码时启用
├── .env.example                # 后续存放模型 Key 和 Java 后端地址示例
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口，后续实现
│   ├── api/
│   │   └── v1/
│   ├── core/
│   ├── clients/
│   ├── llm/
│   ├── agents/
│   ├── prompts/
│   ├── tools/
│   ├── schemas/
│   └── rag/
└── tests/
```

---

## 5. 阶段落地建议

### 第 3 阶段：Agent 对话最小闭环

优先实现：

1. FastAPI 工程骨架；
2. `/api/v1/agent/chat`；
3. DeepSeek 模型调用适配；
4. Java 调 Python 的 HTTP 客户端；
5. 流式输出；
6. `agent_session`、`agent_message`、`agent_trace` 协作记录。

### 第 4 阶段：工具调用

优先实现：

1. Java 工具 API；
2. Python 工具注册表；
3. 项目概览查询；
4. 任务列表查询；
5. 需求拆解草稿；
6. 周报草稿生成。

### 第 5 阶段：风险分析

优先实现：

1. Java 规则扫描；
2. Python 生成风险说明；
3. RabbitMQ 异步任务；
4. 风险候选人工确认。

### 第 6 阶段：RAG 知识库

优先实现：

1. 文档上传和解析；
2. 切片与摘要；
3. 向量检索；
4. 知识问答；
5. 引用来源展示。

---

## 6. 给 Python 初学者的开发建议

如果之前没有 Python 开发经验，建议按这个顺序学习和开发：

```text
1. Python 基础语法
2. 虚拟环境和依赖管理
3. FastAPI 路由和 Pydantic 模型
4. HTTP 客户端调用 Java API
5. 调用 DeepSeek 模型
6. 流式输出
7. Agent 工具调用
8. RAG
```

第一版不要追求复杂框架，不建议一开始就引入 LangChain / LlamaIndex。先用简单、可读、可控的自研轻量编排。


---

## 7. 第 3 阶段最小 Demo 运行说明

本 Demo 已实现一个最小 Agent 对话闭环，目标是帮助理解运转规则，而不是一次性完成全部业务能力。

### 7.1 Demo 已包含

| 能力 | 说明 |
|---|---|
| FastAPI 服务 | 入口为 `app/main.py` |
| 健康检查 | `GET /internal/health` |
| 非流式对话 | `POST /api/v1/agent/chat`，`stream=false` |
| SSE 流式对话 | `POST /api/v1/agent/chat`，`stream=true` |
| DeepSeek V4-pro 适配 | 默认模型名为 `deepseek-v4-pro` |
| 本地 Demo 模式 | 不配置 `DEEPSEEK_API_KEY` 时不会真实调用外部模型 |
| 工具调用演示 | `demo_query_project_overview` 返回固定项目概览数据 |

### 7.2 Demo 运转链路

```text
用户请求
  ↓
FastAPI 路由 app/api/v1/agent.py
  ↓
ProjectChatAgent 编排
  ↓
可选调用 Demo 工具 demo_query_project_overview
  ↓
构造 Prompt
  ↓
DeepSeekClient 调用 deepseek-v4-pro 或本地 Demo 回答
  ↓
返回 JSON 或 SSE 事件流
```

### 7.3 安装依赖

进入 Python 服务目录：

```bash
cd agent-service
```

创建虚拟环境：

```bash
python -m venv .venv
```

Windows Git Bash 激活：

```bash
source .venv/Scripts/activate
```

安装依赖：

```bash
pip install -e .
```

### 7.4 配置环境变量

复制配置文件：

```bash
cp .env.example .env
```

如果只是体验 Demo，可以保持：

```text
DEEPSEEK_API_KEY=
```

此时服务会进入本地 Demo 模式，不真实调用 DeepSeek。

如果要真实调用 DeepSeek V4-pro，填写：

```text
DEEPSEEK_API_KEY=你的 DeepSeek Key
DEEPSEEK_MODEL=deepseek-v4-pro
```

> 如果 DeepSeek 官方实际模型 ID 与 `deepseek-v4-pro` 不一致，只需要修改 `.env` 中的 `DEEPSEEK_MODEL`。

### 7.5 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

启动后访问接口文档：

```text
http://127.0.0.1:8001/docs
```

健康检查：

```bash
curl http://127.0.0.1:8001/internal/health
```

### 7.6 非流式对话测试

```bash
curl -X POST http://127.0.0.1:8001/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -H "X-User-Id: 1" \
  -H "X-Tenant-Id: 0" \
  -d '{
    "message": "帮我看看当前项目任务情况",
    "project_id": 1,
    "stream": false,
    "use_tool_demo": true
  }'
```

预期结果：

- 返回统一结构：`code/message/data/traceId`；
- `data.model` 为 `deepseek-v4-pro`；
- 未配置 Key 时 `data.demo_mode=true`；
- `data.tool_calls` 中包含 `demo_query_project_overview`。

### 7.7 流式对话测试

```bash
curl -N -X POST http://127.0.0.1:8001/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: demo-trace-002" \
  -H "X-User-Id: 1" \
  -H "X-Tenant-Id: 0" \
  -d '{
    "message": "用流式方式说明项目状态",
    "project_id": 1,
    "stream": true,
    "use_tool_demo": true
  }'
```

会看到类似 SSE 事件：

```text
event: meta
data: {...}

event: tool_call
data: {...}

event: token
data: ...

event: done
data: {...}
```

### 7.8 当前 Demo 的边界

当前 Demo 只用于理解 Agent 运转规则，暂不实现：

- Java 调 Python 的后端接口；
- Python 真实调用 Java 工具 API；
- Agent Trace 落库；
- 会话历史落库；
- 前端页面对接；
- RAG；
- 高风险动作确认卡片。

这些内容会在第 3 阶段正式联调和第 4 阶段工具调用中逐步补齐。
