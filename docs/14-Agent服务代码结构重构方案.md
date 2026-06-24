# Agent 服务代码结构重构方案

## 1. 背景

当前 `agent-service` 已经承载 Agent 对话、模型调用、项目上下文扫描、用户习惯 Prompt、MinIO 文件上传、RAG 评测和训练实验等多类代码。随着 MinIO、Qwen 本地模型、用户习惯识别和后续 RAG 能力继续接入，现有目录容易出现以下问题：

1. 运行时代码、业务代码、基础设施代码和实验训练代码边界不清；
2. API 层重复接收 `userId`、`traceId`、`tenantId` 等请求头，接口函数参数臃肿；
3. MinIO、Qdrant、模型客户端等基础设施调用容易散落在业务模块中；
4. Prompt、工具调用、LLM 编排和项目业务混在一起，后续不利于测试和替换模型；
5. RAG 与训练相关代码如果继续混入运行时主链路，会增加维护成本。

因此需要对 `agent-service` 做一次结构化重构，明确运行时边界、业务边界和扩展边界。

## 2. 目标

1. 将 Agent 服务拆分为清晰的运行时模块、项目业务模块、LLM 编排模块、RAG 扩展模块和训练目录；
2. 通过 FastAPI 中间件统一接收并管理 `X-Trace-Id`、`X-User-Id`、`X-Tenant-Id`；
3. 使用 `contextvars.ContextVar` 管理请求上下文，避免在每个接口重复声明请求头；
4. 统一 Python 文件内部代码顺序、命名规范和模块导出规则；
5. 保留当前已实现能力，不引入与正式业务代码无关的额外改动；
6. 为后续 Qwen 本地模型、RAG、项目文件管理和用户习惯识别提供稳定扩展位置。

## 3. 范围

### 3.1 本期范围

本方案覆盖 `agent-service` 的代码结构重构设计，包括：

1. 目录结构调整；
2. 请求上下文统一管理；
3. API、Service、Infrastructure、LLM、Project、RAG、Training 的职责边界；
4. MinIO 文件链路的推荐归属；
5. Qwen 本地模型调用的推荐归属；
6. 代码风格和模块导出规范；
7. 分阶段迁移计划和验收标准。

### 3.2 不做范围

本方案不包含以下内容：

1. 不实现完整 RAG 链路；
2. 不修改 Java 后端业务逻辑；
3. 不修改前端页面；
4. 不设计新的数据库表；
5. 不新增非必要中间件；
6. 不迁移与正式业务代码无关的临时实验文件，除非它们会影响运行时结构；
7. 不将训练代码混入 FastAPI 运行时包。

## 4. 总体分层设计

### 4.1 推荐目录结构

```text
agent-service/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       ├── agent.py
│   │       ├── project_files.py
│   │       ├── project_context.py
│   │       └── user_habits.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── middleware.py
│   │   └── request_context.py
│   │
│   ├── infrastructure/
│   │   ├── http_client.py
│   │   ├── minio_client.py
│   │   └── qdrant_client.py
│   │
│   ├── llm/
│   │   ├── clients/
│   │   │   ├── base.py
│   │   │   ├── deepseek_client.py
│   │   │   ├── doubao_client.py
│   │   │   └── qwen_client.py
│   │   ├── prompts/
│   │   │   ├── project_chat.py
│   │   │   ├── project_context.py
│   │   │   └── user_habits.py
│   │   ├── tools/
│   │   │   ├── registry.py
│   │   │   └── schemas.py
│   │   └── orchestration/
│   │       ├── project_chat_agent.py
│   │       └── user_habit_agent.py
│   │
│   ├── project/
│   │   ├── files/
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── storage.py
│   │   ├── context/
│   │   │   ├── scanner/
│   │   │   ├── indexer/
│   │   │   ├── inspector/
│   │   │   ├── model/
│   │   │   └── service.py
│   │   └── habits/
│   │       ├── prompts.py
│   │       ├── schemas.py
│   │       └── service.py
│   │
│   ├── rag/
│   │   ├── ingestion/
│   │   ├── chunking/
│   │   ├── embedding/
│   │   ├── retrieval/
│   │   └── schemas.py
│   │
│   └── schemas/
│       ├── common.py
│       ├── errors.py
│       └── response.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── training/
    ├── configs/
    ├── datasets/
    ├── scripts/
    └── README.md
```

### 4.2 分层职责

| 层级 | 目录 | 职责 | 不应承担的职责 |
|---|---|---|---|
| 接口层 | `app/api/v1` | FastAPI 路由、请求参数接收、响应返回 | 不直接调用 MinIO、Qdrant、LLM SDK |
| 核心层 | `app/core` | 配置、日志、中间件、请求上下文 | 不写具体业务逻辑 |
| 基础设施层 | `app/infrastructure` | MinIO、Qdrant、HTTP 客户端等底层封装 | 不写项目业务规则 |
| LLM 层 | `app/llm` | 模型客户端、Prompt、工具注册、Agent 编排 | 不直接处理项目文件路径和业务状态 |
| 项目业务层 | `app/project` | 项目文件、项目上下文、用户习惯等业务能力 | 不直接初始化底层 SDK |
| RAG 层 | `app/rag` | 后续知识库摄取、切片、向量化、检索 | 不提前实现完整 RAG 闭环 |
| 通用 Schema 层 | `app/schemas` | 错误码、统一响应、公共结构 | 不放具体业务模型 |
| 训练目录 | `training` | Qwen 本地训练数据、脚本、配置 | 不参与 FastAPI 运行时导入 |

## 5. 目录拆分合理性说明

### 5.1 `app` 不建议改名

`app` 是 FastAPI 运行时 Python 包根目录，建议保留。用户提出的“`app` 用于存放和 LLM 交互部分代码”可以落到 `app/llm`，而不是把整个 `app` 变成 LLM 专属目录。

原因：

1. `app.main:app` 是当前服务启动入口；
2. `app` 通常表示运行时应用包；
3. 如果将 `app` 限定为 LLM，会导致 API、core、project、rag 都缺少统一根包。

### 5.2 `project` 适合承载用户项目业务

`project` 适合放用户项目相关的业务能力，例如：

1. 项目文件上传与管理；
2. 项目上下文扫描和索引；
3. 用户习惯识别与融合；
4. 面向项目的模型能力调用封装。

但 MinIO SDK 初始化不应放在 `project`，而应放在 `infrastructure`。项目文件服务只关心“文件如何按业务规则存储”，不关心底层 SDK 如何连接。

### 5.3 `rag` 使用小写命名

Python 包名建议统一小写，因此使用 `rag`，不使用 `RAG`。

`rag` 目录本期只保留扩展位置，后续第 6 阶段再逐步实现：

1. 文档摄取；
2. 文档切片；
3. 向量化；
4. 向量检索；
5. RAG 问答生成。

### 5.4 `training` 不放入运行时主链路

训练相关目录建议放在 `agent-service/training`，不放在 `app` 内。

原因：

1. 训练脚本通常依赖 GPU、数据集、模型权重和独立环境；
2. 训练代码不应被 FastAPI 启动时导入；
3. 训练产物与运行时接口的生命周期不同；
4. 可以避免运行时镜像被训练依赖拖重。

如果未来训练能力上升为仓库级能力，也可以迁移到仓库根目录 `training/`。

## 6. 请求上下文统一管理设计

### 6.1 设计目标

统一管理以下请求头：

| 请求头 | 用途 | 是否自动生成 |
|---|---|---|
| `X-Trace-Id` | 链路追踪 | 缺失时自动生成 |
| `X-User-Id` | 当前用户 | 不自动生成 |
| `X-Tenant-Id` | 当前租户 | 不自动生成 |
| `X-Idempotency-Key` | 写接口幂等键 | 不自动生成，写接口单独校验 |

`X-Trace-Id`、`X-User-Id`、`X-Tenant-Id` 由中间件统一读取并写入请求上下文；业务代码通过 `get_request_context()` 获取。

### 6.2 为什么不用线程变量

FastAPI 支持异步请求处理，同一个线程中可能同时运行多个请求协程。传统 `threading.local()` 不适合作为请求上下文容器。

推荐使用：

```python
contextvars.ContextVar
```

它可以在异步协程上下文中隔离不同请求的数据，语义更接近异步场景下的 ThreadLocal。

### 6.3 推荐文件

```text
app/core/request_context.py
app/core/middleware.py
```

### 6.4 `request_context.py` 推荐结构

```python
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class RequestContext:
    trace_id: str
    user_id: str | None
    tenant_id: str | None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def set_request_context(context: RequestContext):
    return _request_context.set(context)


def reset_request_context(token) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext:
    context = _request_context.get()
    if context is None:
        raise RuntimeError("当前请求上下文不存在")
    return context


__all__ = [
    "RequestContext",
    "set_request_context",
    "reset_request_context",
    "get_request_context",
]
```

### 6.5 `middleware.py` 推荐结构

```python
from uuid import uuid4

from fastapi import Request

from app.core.request_context import (
    RequestContext,
    reset_request_context,
    set_request_context,
)


async def request_context_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
    user_id = request.headers.get("X-User-Id")
    tenant_id = request.headers.get("X-Tenant-Id")

    token = set_request_context(
        RequestContext(
            trace_id=trace_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
    )

    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        reset_request_context(token)


__all__ = ["request_context_middleware"]
```

### 6.6 API 层使用方式

接口层不再重复写：

```python
x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")
x_user_id: str | None = Header(default=None, alias="X-User-Id")
x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id")
```

改为：

```python
from app.core.request_context import get_request_context

context = get_request_context()
```

写接口仍保留 `X-Idempotency-Key` 的显式校验，因为它不是通用上下文，而是写操作防重复提交约束。

## 7. MinIO 文件链路重构设计

### 7.1 当前能力归属

MinIO 文件能力应拆为三层：

| 层级 | 推荐文件 | 职责 |
|---|---|---|
| API | `app/api/v1/project_files.py` | 接收上传、查询、下载、更新、删除请求 |
| Project Service | `app/project/files/service.py` | 项目文件业务规则、用户归属校验、业务分区 |
| Infrastructure | `app/infrastructure/minio_client.py` | MinIO Client 初始化、Bucket 创建、对象读写封装 |

### 7.2 存储路径规则

上传文件时，业务对象路径统一为：

```text
PM-AGENT/{userId}/{projectId}/{business}/{file}
```

其中：

| 字段 | 说明 |
|---|---|
| `PM-AGENT` | 系统固定前缀 |
| `userId` | 当前用户 ID |
| `projectId` | 当前项目 ID |
| `business` | 业务名，只允许 `project`、`system`、`user` |
| `file` | 实际文件名，建议加短 UUID 前缀防重名 |

### 7.3 API 推荐命名

```text
POST   /api/v1/project/files
GET    /api/v1/project/files
GET    /api/v1/project/files/download
PUT    /api/v1/project/files
DELETE /api/v1/project/files
```

说明：

1. 上传使用 `multipart/form-data`；
2. 查询、下载、更新、删除通过 `urlPath` 定位文件；
3. 写操作必须校验 `X-Idempotency-Key`；
4. 用户归属从请求上下文中获取，不在接口层重复声明 `X-User-Id`。

### 7.4 不建议的做法

1. 不建议在 API 路由中直接初始化 `Minio`；
2. 不建议把 MinIO bucket、endpoint 等配置写死在业务代码中；
3. 不建议对完整 URL 不做 host 校验就执行删除；
4. 不建议把文件元数据直接混入 RAG 代码；
5. 不建议用 MinIO 代替 MySQL 的文件元数据管理。

## 8. LLM 与 Qwen 调用重构设计

### 8.1 LLM 目录职责

`app/llm` 负责所有模型相关能力：

1. DeepSeek、豆包、Qwen 等模型客户端；
2. Prompt 模板；
3. 工具注册；
4. Agent 编排；
5. 模型路由；
6. 模型输出结构化解析。

### 8.2 Qwen 归属

Qwen 本地部署模型调用属于模型客户端，不应直接放在 `project` 下。

推荐位置：

```text
app/llm/clients/qwen_client.py
```

项目业务如果需要调用 Qwen，应通过业务 service 调用 LLM 编排层，例如：

```text
app/project/habits/service.py
    -> app/llm/orchestration/user_habit_agent.py
        -> app/llm/clients/qwen_client.py
```

这样可以保证：

1. 项目业务不绑定具体模型；
2. 后续 DeepSeek、Qwen、Claude、GPT 可替换；
3. 模型调用 Trace 更容易统一记录；
4. Prompt 不散落在项目业务逻辑中。

### 8.3 Prompt 归属

推荐按能力拆分 Prompt：

```text
app/llm/prompts/project_chat.py
app/llm/prompts/project_context.py
app/llm/prompts/user_habits.py
```

Prompt 文件只负责模板和格式说明，不负责发起模型请求。

## 9. RAG 与训练目录设计

### 9.1 RAG 目录

`app/rag` 作为第 6 阶段知识库能力预留目录，本期可以先保留空目录或最小包结构。

推荐拆分：

| 子目录 | 职责 |
|---|---|
| `ingestion` | 文档接入、解析任务入口 |
| `chunking` | 文档切片规则 |
| `embedding` | 向量化调用 |
| `retrieval` | 检索策略 |
| `schemas.py` | RAG 相关结构 |

### 9.2 Training 目录

`training` 用于 Qwen 本地模型训练、微调、评测和数据处理。

推荐结构：

```text
training/
├── configs/
├── datasets/
├── scripts/
└── README.md
```

训练代码不应被 `app/main.py` 或任意 FastAPI 运行时模块导入。

## 10. 统一代码风格

### 10.1 文件内部顺序

每个 Python 文件统一按以下顺序组织：

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

### 10.2 API 文件顺序

API 文件建议：

```python
router = APIRouter(...)


@router.post(...)
async def upload_project_file(...):
    ...


@router.get(...)
def get_project_file(...):
    ...


def _validate_idempotency_key(...):
    ...
```

路由函数放在上方，内部校验和转换方法放在下方。

### 10.3 Service 文件顺序

Service 文件建议：

```python
class ProjectFileService:
    def upload_file(...):
        ...

    def get_file(...):
        ...

    def replace_file(...):
        ...

    def delete_file(...):
        ...

    def _build_object_name(...):
        ...

    def _parse_url_path(...):
        ...
```

对外业务方法放在上方，文件内部管理方法放在下方。

### 10.4 命名规范

1. Python 包名、文件名使用小写下划线；
2. 函数和变量使用小写下划线；
3. 类名使用大驼峰；
4. 内部方法使用单下划线前缀；
5. 不使用 Java 风格的小驼峰函数名；
6. Pydantic 字段如需对外兼容 `userId`，内部可使用 `user_id` 并通过 alias 处理。

### 10.5 `__all__` 规范

每个对外包入口或核心模块应声明 `__all__`，明确对外可用对象。

示例：

```python
__all__ = [
    "ProjectFileService",
    "FileBusiness",
    "FileUploadResult",
]
```

说明：

1. `__all__` 用于表达模块导出边界；
2. `__all__` 不是安全机制；
3. 私有方法仍需以下划线命名；
4. 包级 `__init__.py` 可通过 `__all__` 控制统一导出。

## 11. 迁移计划

### 11.1 第一阶段：请求上下文与文件模块收敛

目标：优先减少接口层臃肿，稳定 MinIO 文件链路。

改动内容：

1. 新增 `app/core/request_context.py`；
2. 新增 `app/core/middleware.py`；
3. 在 `app/main.py` 注册请求上下文中间件；
4. 将 `app/api/v1/files.py` 重命名或迁移为 `app/api/v1/project_files.py`；
5. 将 `app/services/file_storage.py` 拆分为：
   - `app/infrastructure/minio_client.py`
   - `app/project/files/service.py`
   - `app/project/files/storage.py`
6. 将 `app/schemas/files.py` 迁移到 `app/project/files/schemas.py`；
7. 在 API 层移除重复的 `X-Trace-Id`、`X-User-Id`、`X-Tenant-Id` 参数。

验收标准：

1. 文件上传、查询、下载、覆盖更新、删除链路全部可用；
2. 响应头包含 `X-Trace-Id`；
3. 业务代码可通过 `get_request_context()` 获取当前请求上下文；
4. 写接口仍能校验 `X-Idempotency-Key`；
5. MinIO Client 只在基础设施层初始化。

### 11.2 第二阶段：LLM、Prompt 与项目业务分离

目标：把模型调用能力和项目业务能力解耦。

改动内容：

1. 将模型客户端整理到 `app/llm/clients`；
2. 将 Prompt 模板整理到 `app/llm/prompts`；
3. 将 Agent 编排整理到 `app/llm/orchestration`；
4. 将工具注册和工具 schema 整理到 `app/llm/tools`；
5. 将项目上下文业务整理到 `app/project/context`；
6. 将用户习惯业务整理到 `app/project/habits`。

验收标准：

1. 项目业务不直接依赖具体模型 SDK；
2. Prompt 文件不发起模型请求；
3. 模型客户端不包含项目业务规则；
4. Agent 对话接口保持兼容。

### 11.3 第三阶段：RAG 与 training 独立

目标：为第 6 阶段 RAG 和本地模型训练预留清晰边界。

改动内容：

1. 新建或整理 `app/rag` 包结构；
2. 将 RAG 评测、切片、向量检索相关代码迁移到 `app/rag` 或 `training` 中合适位置；
3. 将 Qwen 本地训练脚本、数据处理脚本和配置迁移到 `training`；
4. 确保 `training` 不被 FastAPI 运行时导入。

验收标准：

1. 启动 FastAPI 不依赖训练环境；
2. RAG 代码不会影响当前 Agent 对话和文件接口；
3. 训练脚本可以独立运行；
4. 运行时代码和训练代码边界清晰。

## 12. 风险与取舍

| 风险 | 说明 | 应对策略 |
|---|---|---|
| 一次性迁移过大 | 全量移动文件可能造成导入路径大量失效 | 按三阶段迁移，每阶段运行测试 |
| API 路径变化影响调用方 | `files.py` 迁移为 `project_files.py` 可能影响前端或 Java 后端 | 可保持旧路径短期兼容，正式文档以新路径为准 |
| 请求上下文误用 | 异步场景下使用 ThreadLocal 会串请求 | 使用 `contextvars.ContextVar` |
| MinIO 与项目业务耦合 | 业务代码直接依赖 MinIO SDK 会影响替换存储 | SDK 初始化放 `infrastructure` |
| RAG 提前膨胀 | 过早实现完整 RAG 会偏离当前阶段 | 本期只整理边界，不实现完整 RAG |
| 训练依赖污染运行时 | GPU、训练依赖可能拖慢服务部署 | `training` 不进入 `app` 包 |

## 13. 验收标准

重构完成后，应满足以下标准：

1. `agent-service` 可以正常启动；
2. `/internal/health` 正常返回；
3. `/api/v1/agent/chat` 原有能力不回退；
4. 项目文件上传、查询、下载、覆盖更新、删除可用；
5. 所有请求响应头包含 `X-Trace-Id`；
6. API 层不再重复声明 `X-Trace-Id`、`X-User-Id`、`X-Tenant-Id`；
7. 写接口仍显式校验 `X-Idempotency-Key`；
8. MinIO、Qdrant、HTTP 客户端只在 `infrastructure` 层封装；
9. LLM 客户端、Prompt、工具调用和 Agent 编排位于 `app/llm`；
10. 用户项目业务位于 `app/project`；
11. RAG 扩展位于 `app/rag`；
12. 训练相关文件位于 `training`，且不被运行时导入；
13. Python 文件使用小写下划线命名；
14. 对外模块通过 `__all__` 明确导出对象；
15. 单元测试和集成测试目录分离。

## 14. 建议测试顺序

### 14.1 静态检查

```bash
python -m compileall agent-service/app
```

### 14.2 服务启动检查

```bash
cd agent-service
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 14.3 健康检查

```bash
curl http://127.0.0.1:8000/internal/health
```

### 14.4 文件链路检查

按顺序验证：

1. 上传文件；
2. 查询文件元信息；
3. 下载文件；
4. 覆盖更新文件；
5. 再次下载确认内容变化；
6. 删除文件；
7. 再次查询确认文件不存在。

### 14.5 Agent 对话检查

验证 `/api/v1/agent/chat` 非流式与流式调用均正常。

### 14.6 请求上下文检查

验证：

1. 未传 `X-Trace-Id` 时自动生成；
2. 传入 `X-Trace-Id` 时响应头原样返回；
3. 业务方法可读取 `user_id` 和 `tenant_id`；
4. 并发请求之间上下文不串值。

## 15. 待确认问题

1. 文件接口是否正式从 `/api/v1/files` 调整为 `/api/v1/project/files`，还是保留旧路径兼容一段时间；调整
2. `system` 业务文件是否允许普通用户上传，还是仅允许 Java 后端或管理员调用；允许
3. `training` 最终放在 `agent-service/training`，还是提升到仓库根目录 `training`；agent-service/training
4. 用户习惯识别是否作为 `project/habits` 的正式业务能力，还是先放在 `llm/prompts` 中作为 Prompt 能力保留；作为 `project/habits` 的正式业务能力
5. RAG 目录本期是否只保留空包结构，还是同步迁移现有评测与数据处理脚本。空包
