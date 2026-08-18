# PM-Agent Python 单体后端

`agent-service/` 是 PM-Agent 的唯一在线后端，统一承载认证、用户、项目、项目文件、文件分析和 Agent 对话能力。

```text
Vue 3 → FastAPI 模块化单体 → MySQL / Redis / MinIO / LLM
```

- Python 是业务表的唯一写入者。
- Alembic 是数据库结构的唯一迁移工具。
- Java 不再是运行依赖，Python 内部不存在 Java/Python 业务 HTTP 自调用。
- Agent 工具只能调用业务模块公开 Service，不能直接获取数据库 Session 或执行任意 SQL。
- MinIO、LLM 等外部调用不得占用数据库事务。

## 当前开发进度

| 范围 | 状态 | 当前能力 |
|---|---|---|
| Python 单体迁移 | 已完成 | 在线认证、用户、项目和文件链路已收敛到 FastAPI |
| 公共基础设施 | 已完成 | 配置、统一响应、全局异常、日志、`traceId`、JWT、幂等、MySQL、Redis、MinIO |
| 认证与用户 | 已完成 | 注册、登录、注销、当前用户资料、资料修改和密码修改 |
| 项目 | 已完成 | 创建、初始化索引、列表、详情、归属校验和删除 |
| 项目文件管理 | 已完成 | 上传、覆盖、路径修改、列表、预签名读取地址、删除、幂等和乐观锁 |
| 项目文件分析 | 第一版已完成 | 读取源文件、调用分析器、写入文件详情、更新分析投影并重建项目索引 |
| Agent 对话 | 基础能力可用 | 提供 `/api/v1/agent/chat` 普通响应和 SSE 流式响应，仍需继续完善业务工具、场景回归和 Agent Trace 持久化 |
| 数据库迁移 | 已完成基线 | Alembic 管理 `pm_user`、`pm_project` 和 `pm_project_file` |
| 单元测试 | 已完成当前模块 | `auth`、`user`、`project`、`project_file` 共 94 项测试 |
| HTTP 手工调用 | 已完成 | `test_client/` 提供 26 个可按业务流程执行的 `.http` 请求 |
| 需求、任务、迭代、风险、报告 | 尚未实现 | 属于后续业务阶段，不在当前后端闭环内 |
| 完整 RAG、训练与评测 | 未接入在线主链路 | 保留现有基础代码和独立资产，不作为当前已交付能力 |

开发进度以当前分支代码和自动化测试结果为准，不将目录占位或实验代码视为已经完成的在线功能。

## 目录结构

```text
agent-service/
├── app/
│   ├── main.py                         FastAPI 入口与启动、关闭生命周期
│   ├── api/v1/                         V1 路由聚合与 Agent API
│   ├── core/
│   │   ├── config/                     环境配置
│   │   ├── errors/                     错误码、业务异常和全局异常处理
│   │   ├── idempotency/                Redis 幂等门禁
│   │   ├── response/                   统一响应结构
│   │   ├── security/                   JWT、密码和当前用户依赖
│   │   ├── trace/                      traceId 上下文与中间件
│   │   └── logger.py                   日志配置与 traceId 注入
│   ├── infrastructure/
│   │   ├── database/                   SQLAlchemy Engine、Session、Base 和模型注册
│   │   ├── redis/                      Redis 客户端和登录会话
│   │   └── storage/                    MinIO 客户端与对象路径
│   ├── modules/
│   │   ├── auth/                       注册、登录和注销
│   │   ├── user/                       用户资料与密码
│   │   ├── project/                    项目生命周期与索引
│   │   └── project_file/
│   │       ├── api.py                  文件路由聚合
│   │       ├── domain.py               共享业务类型和状态
│   │       ├── models.py               ProjectFile ORM
│   │       ├── repository.py           文件表持久化网关
│   │       ├── management/             源文件管理与 MinIO 生命周期
│   │       └── analysis/               文件分析与派生结果写入
│   ├── agents/                         Agent 兼容入口
│   ├── llm/                            模型客户端、路由、Prompt 和编排
│   ├── project/context/                项目上下文、文件解析和模型适配
│   ├── normalization/                  内容归一化公共能力
│   ├── memory/                         记忆能力基础结构
│   ├── rag/                            RAG 基础结构
│   └── streaming/                      SSE 事件和响应载荷
├── migrations/
│   ├── env.py                          Alembic 异步迁移环境
│   └── versions/                       数据库版本脚本
├── tests/unit/modules/                 按业务模块分层的单元测试
├── test_client/                        按业务模块分层的手工 HTTP 请求
├── docs/                               Agent 服务专项文档
├── project_test/                       受保护的项目实验
├── alembic.ini                         Alembic 配置
├── pyproject.toml                      项目信息及运行、开发依赖权威清单
├── pytest.ini                          pytest 配置
├── .env.example                        环境变量模板
└── README.md
```

脚本、评测、训练、归一化演示、示例和词库资源已迁移至仓库根目录的本地留档区 `archive/agent-service-deferred/`。该目录被 `.gitignore` 忽略，主业务完成后再恢复并优化。

`.venv/`、`.pytest_cache/`、`.ruff_cache/`、`__pycache__/` 和 `pm_agent_service.egg-info/` 都是本地环境或工具生成目录，不属于需要维护的业务源码。`pm_agent_service.egg-info/` 会在可编辑安装时自动生成，依赖的权威来源仍是 `pyproject.toml`。

## 业务模块分层

普通在线业务模块采用以下垂直分层：

| 文件 | 职责 |
|---|---|
| `api.py` | HTTP 参数、认证依赖和统一响应，不编写业务逻辑 |
| `schemas.py` | Pydantic 请求、响应和内部传输模型 |
| `models.py` | SQLAlchemy ORM 模型 |
| `domain.py` | 状态枚举、状态转换和纯业务规则 |
| `repository.py` | 数据库查询与持久化 |
| `service.py` | 事务边界和业务编排 |
| `errors.py` | 模块错误定义 |

`project_file` 进一步拆成两个子包：

- `management/`：独占源文件上传、覆盖、改名、删除、列表、预签名 URL、幂等控制、乐观锁和状态机。
- `analysis/`：只读取源文件、调用分析器、写入 `system/file_details/*.json`、更新分析投影并重建索引，不得改名或删除用户源文件。
- 两个子包共享根目录的 ORM、状态枚举和 Repository，不得互相导入 Service。

## 环境要求

- Python 3.11 或更高版本。
- MySQL 8.x。
- Redis 6.x 或兼容版本。
- MinIO。
- Agent 对话和模型增强分析需要配置可用的 LLM Provider；认证、用户、项目和文件管理接口不依赖模型密钥。

所有本地配置从 `.env.example` 复制到 `.env` 后修改。`.env` 包含数据库密码、JWT 密钥和模型密钥，不得提交 Git。

## 安装中间件

如果使用仓库提供的 Docker Compose，请在项目根目录执行：

```powershell
Copy-Item deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql redis minio
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

在 Bash 中可将 `Copy-Item` 替换为：

```bash
cp deploy/.env.example deploy/.env
```

Docker Compose 负责创建和启动 MySQL、Redis、MinIO，并创建空数据库；业务表仍由 Alembic 创建。

## 创建 Python 环境

在项目根目录进入后端：

```powershell
cd agent-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Git Bash 可使用：

```bash
source .venv/Scripts/activate
cp .env.example .env
```

## 安装所需依赖

在 `agent-service/` 目录执行：

```powershell
python -m pip install -e ".[dev]"
```

主要运行依赖包括 FastAPI、Uvicorn、SQLAlchemy、AsyncMy、Alembic、Redis、MinIO、PyJWT、pwdlib、Pydantic 和 HTTPX；开发依赖包括 pytest、Ruff 和 aiosqlite。不要手动维护 `pm_agent_service.egg-info/` 中的依赖副本。

## 创建或升级数据库表

FastAPI 启动时只检查数据库连通性，不会调用 `Base.metadata.create_all()`，因此不会自动建表。首次启动或拉取新的迁移后，必须在 `agent-service/` 目录显式执行：

```powershell
python -m alembic current
python -m alembic upgrade head
python -m alembic current
```

其中真正创建或升级表结构的命令是：

```powershell
python -m alembic upgrade head
```

全新数据库会创建：

- `alembic_version`：记录当前迁移版本；
- `pm_user`：用户；
- `pm_project`：项目；
- `pm_project_file`：项目文件及分析投影。

注意事项：

- `PM_AGENT_DATABASE_URL` 指向的数据库必须已经存在；
- 数据库用户必须拥有建表、建索引和修改表结构的权限；
- Alembic 从 `.env` 读取实际数据库地址，不要依赖 `alembic.ini` 中的示例地址；
- 不使用 `create_all()` 绕过 Alembic，也不直接改写已经应用的迁移脚本；
- 新的数据库结构变更必须新增 revision。

只生成迁移 SQL、不实际执行时可使用：

```powershell
python -m alembic upgrade head --sql
```

## 启动后端

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
GET http://localhost:8000/internal/health
```

前端 Vite 将 `/api` 代理到 `http://localhost:8000`。

## 接口范围

| 模块 | 路径前缀 | 当前接口 |
|---|---|---|
| 认证 | `/api/v1/auth` | 注册、登录、注销 |
| 用户 | `/api/v1/users` | 当前用户查询、资料修改、密码修改 |
| 项目 | `/api/v1/projects` | 创建、列表、详情、删除 |
| 项目文件 | `/api/v1/projects/{projectId}/files` | 上传、覆盖、改名、列表、读取地址、删除、初始化解析 |
| Agent | `/api/v1/agent` | 项目问答与 SSE 流式响应 |

业务响应统一包含：

```json
{
  "code": 200,
  "message": "成功",
  "data": null,
  "traceId": "当前请求的链路标识"
}
```

认证使用 `Authorization: Bearer <JWT>`，写文件接口还需要 `X-Idempotency-Key`。请求和响应通过 `X-Trace-Id`、`traceId` 关联日志。

## 文件解析链路

`POST /api/v1/projects/{projectId}/files/parse/init` 在同一 Python 进程内完成：

1. 从 MySQL 查询尚未解析的活动文件；
2. 通过 MinIO SDK 按对象键读取内容；
3. 调用本地解析器和模型适配器；
4. 使用 Pydantic 校验结构和文件身份字段；
5. 写入 `system/file_details/*.json`；
6. 条件更新分析投影和解析次数；
7. 从数据库全量重建 `system/index.json`。

`index.json` 是可重建快照，不是业务权威数据源。文件分析服务只能读取源文件并写入派生结果。

## 测试与手工验证

运行完整单元测试：

```powershell
python -m pytest
```

当前测试按以下路径组织：

```text
tests/unit/modules/
├── auth/
├── user/
├── project/
└── project_file/
    ├── management/
    └── analysis/
```

HTTP 手工调用位于 `test_client/`。在 JetBrains HTTP Client 中选择 `dev` 环境后，按照 `test_client/README.md` 的顺序执行，可验证注册、登录、项目创建、文件上传、文件分析和清理流程。

## 开发约束

- API 不直接访问 MySQL、Redis、MinIO 或 LLM。
- Service 不依赖 FastAPI Request，不拼装 HTTP 响应。
- Repository 不调用其他 Repository、MinIO、Redis 或 LLM。
- ORM 模型不直接作为 API 响应返回。
- 跨模块协作只使用公开 Service。
- Agent 工具不得获得 SQLAlchemy Session。
- 数据库结构变更只通过新的 Alembic revision 完成。
- 不在数据库事务中执行 MinIO 或 LLM 调用。
- 不提交 `.env`、`.venv`、缓存、`*.egg-info/`、训练数据、评测输出或模型产物。
- `archive/agent-service-deferred/` 中的本地留档和 `project_test/` 是受保护资产，在线业务开发不得顺带移动或重构。

长期架构和接口口径以项目根目录的 `docs/14-Agent服务代码结构说明.md`、`docs/21-Python单体后端迁移说明.md` 和实际代码为准。
