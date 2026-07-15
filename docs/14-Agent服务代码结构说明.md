# 14 Agent 服务代码结构说明

本文档说明 `agent-service` 当前的代码分层、目录职责、命名规范和扩展边界，是 Agent 服务后续新增能力的归位依据。

历史重构方案与迁移过程不再保留在本文档中，需要时参考 git 历史。

---

## 1. 目录结构

```text
agent-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── internal/                 # 接口对应的内部函数封装，便于业务内部复用
│   │   │   └── minio_files.py
│   │   └── v1/                       # FastAPI 路由
│   │       ├── agent.py
│   │       ├── minio_files.py
│   │       └── project_files.py
│   │
│   ├── core/                         # 配置、日志、请求上下文、中间件
│   │   ├── config/
│   │   ├── logger.py
│   │   ├── middleware.py
│   │   └── request_context.py
│   │
│   ├── infrastructure/               # MinIO、HTTP、向量库等底层客户端
│   │   └── minio_client.py
│   │
│   ├── llm/                          # LLM 客户端、Prompt、工具、Agent 编排
│   │   ├── clients/
│   │   ├── prompts/
│   │   ├── tools/
│   │   └── orchestration/
│   │
│   ├── project/                      # 用户项目相关业务能力
│   │   ├── files/                    # 项目文件上传、存储规则、文件树编排
│   │   ├── context/                  # 项目文件树扫描、索引、模型相关
│   │   └── habits/                   # 用户习惯识别业务
│   │
│   ├── normalization/                # 内容归一化、词库、匹配、映射和版本缓存
│   │
│   ├── rag/                          # 第 6 阶段 RAG 预留位置
│   │
│   ├── memory/                       # 记忆相关预留位置
│   │
│   ├── streaming/                    # SSE 事件、流式输出、metrics
│   │
│   └── schemas/                      # 通用 schema、错误、响应结构
│
├── tests/
│
├── training/                         # Qwen 本地训练数据、脚本、配置
│
└── pyproject.toml
```

---

## 2. 分层职责

| 层级 | 目录 | 职责 | 不应承担的职责 |
|---|---|---|---|
| 接口层 | `app/api/v1` | FastAPI 路由、参数接收、异常包装、响应返回 | 不直接调用 MinIO、向量库、LLM SDK |
| 内部封装层 | `app/api/internal` | 把接口业务逻辑封装为可内部复用的纯函数 | 不携带 FastAPI 装饰器与 HTTP 异常映射 |
| 核心层 | `app/core` | 配置、日志、请求上下文、中间件 | 不写具体业务逻辑 |
| 基础设施层 | `app/infrastructure` | MinIO、HTTP、向量库等底层客户端 | 不写项目业务规则 |
| LLM 层 | `app/llm` | 模型客户端、Prompt、工具注册、Agent 编排 | 不直接处理项目文件路径或业务状态 |
| 项目业务层 | `app/project` | 项目文件、文件树、上下文、用户习惯等业务能力 | 不直接初始化底层 SDK |
| 内容归一化层 | `app/normalization` | 词库加载、校验、合并、匹配、术语映射和版本缓存 | 不负责 BM25F 召回、SimHash 去重或直接修改业务数据 |
| 流式层 | `app/streaming` | SSE 事件、流式 payload、token 统计 | 不写业务规则 |
| RAG 层 | `app/rag` | 文档摄取、切片、向量化、检索 | 当前阶段只保留扩展位置 |
| 记忆层 | `app/memory` | 记忆抽取、检索、存储 | 当前阶段只保留扩展位置 |
| 通用 Schema 层 | `app/schemas` | 错误、统一响应、公共结构 | 不放具体业务模型 |
| 训练目录 | `training` | Qwen 本地训练数据、脚本、配置 | 不被 FastAPI 运行时导入 |

---

## 3. 请求上下文

异步场景下统一使用 `contextvars.ContextVar`，禁止使用 `threading.local()`。

| 请求头 | 用途 | 是否自动生成 |
|---|---|---|
| `X-Trace-Id` | 链路追踪 | 缺失时自动生成 |
| `X-User-Id` | 当前用户 | 不自动生成 |
| `X-Tenant-Id` | 当前租户 | 不自动生成 |

上下文由 `app/core/middleware.py` 中的中间件统一读取并写入 `app/core/request_context.py`，业务层通过 `get_request_context()` 获取。接口层不再重复声明 `X-Trace-Id` / `X-User-Id` / `X-Tenant-Id` 参数。

---

## 4. MinIO 文件链路

| 层级 | 推荐文件 | 职责 |
|---|---|---|
| API 路由 | `app/api/v1/minio_files.py` | 上传 / 查看 / 下载 / 更新 / 删除 HTTP 入口 |
| 内部函数 | `app/api/internal/minio_files.py` | 复用 service 的业务封装，供 `project_files` 等模块直接调用 |
| 文件树编排 | `app/api/v1/project_files.py` | 项目文件树构建与更新 HTTP 入口 |
| 文件树服务 | `app/project/files/tree_service.py` | 文件树扫描、MinIO 同步、`Project_Index.json` 写入 |
| 业务服务 | `app/project/files/service.py` | 文件名规则、用户归属校验、业务分区 |
| 存储规则 | `app/project/files/storage.py` | 对象名、URL、路径解析 |
| 基础设施 | `app/infrastructure/minio_client.py` | MinIO Client 初始化、Bucket 创建、对象读写 |

对象命名规则：

```text
PM-AGENT/{userId}/{projectId}/{business}/{file}
```

`business` 仅允许 `project`、`system`、`user`。

---

## 5. LLM 与模型扩展

`app/llm/` 是模型相关能力的唯一入口：

- `clients/`：DeepSeek、豆包、Qwen 等 Provider 客户端
- `prompts/`：按能力拆分的 Prompt 模板
- `tools/`：工具注册与 schema
- `orchestration/`：Agent 编排，例如 `ProjectChatAgent`

项目业务调用 LLM 必须经过编排层，禁止从 `app/project/*` 直接调用 `clients/`。Qwen 本地模型客户端归属 `app/llm/clients/qwen_client.py`，训练相关脚本归属 `training/`，不进入运行时包。

---

## 6. RAG 与训练

- `app/rag/` 第 6 阶段实现，当前仅保留空包结构。
- `training/` 用于 Qwen 本地训练、数据处理、评测脚本；不被 FastAPI 运行时导入；如未来训练上升为仓库级能力，可迁移到仓库根目录 `training/`。

---

## 7. 代码风格

### 7.1 文件内部顺序

```text
1. 模块 docstring
2. from __future__ import annotations
3. 标准库 import
4. 第三方 import
5. 项目内 import
6. __all__
7. 常量 / 枚举
8. 对外类 / 对外函数 / API 路由函数
9. 文件内部私有方法
```

### 7.2 命名规范

- 包名、文件名使用小写下划线；
- 函数、变量使用小写下划线；
- 类名使用大驼峰；
- 内部方法使用单下划线前缀；
- 不使用 Java 风格的小驼峰函数名；
- Pydantic 字段如需对外兼容 `userId`，内部使用 `user_id` 并通过 alias 处理。

### 7.3 `__all__`

对外包入口或核心模块必须声明 `__all__`，作为对外导出边界，不作为安全机制。

---

## 8. 待确认问题

暂无。后续随 RAG、Qwen、记忆链路落地，再分别在对应模块下补充设计文档。
