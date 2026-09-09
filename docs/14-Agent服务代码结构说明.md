# Python 后端代码结构说明

保留目录名 `agent-service/`，其中同时包含在线业务与既有 Agent 能力。

```text
agent-service/app/
├── main.py
├── api/v1/router.py
├── core/
│   ├── config/
│   ├── response/
│   ├── errors/
│   ├── security/
│   ├── trace/
│   └── idempotency/
├── infrastructure/
│   ├── database/
│   ├── redis/
│   └── storage/
├── agents/
│   ├── dependencies.py
│   └── tools/
│       ├── base.py
│       ├── schemas.py
│       ├── registry.py
│       ├── executor.py
│       └── project/
├── llm/
│   ├── base.py
│   ├── contracts.py
│   ├── structured.py
│   ├── clients/
│   ├── orchestration/
│   └── prompts/
│       ├── project_chat.py
│       ├── project_context/
│       └── memory/
├── modules/
│   ├── auth/
│   ├── user/
│   ├── project/
│   ├── chat/
│   │   ├── api.py
│   │   ├── dependencies.py
│   │   ├── conversation/
│   │   ├── learning/
│   │   ├── context/
│   │   ├── runs/
│   │   └── legacy/
│   ├── report/
│   └── project_file/
│       ├── __init__.py
│       ├── api.py
│       ├── domain.py
│       ├── models.py
│       ├── repository.py
│       ├── management/
│       │   ├── api.py
│       │   ├── domain.py
│       │   ├── schemas.py
│       │   ├── errors.py
│       │   └── service.py
│       └── analysis/
│           ├── api.py
│           └── service.py
├── project_context/
│   ├── file_detail/
│   ├── index/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   └── service.py
│   └── specification/
├── maintenance/
│   └── remove_analysis_version.py
└── input_context、memory、rag
```

普通在线业务模块采用垂直分层：

| 文件 | 职责 |
|---|---|
| `api.py` | HTTP 协议、参数依赖、响应包装 |
| `schemas.py` | 请求、响应与内部 DTO |
| `models.py` | SQLAlchemy 模型 |
| `domain.py` | 枚举、不变量与纯计算 |
| `repository.py` | 本模块数据库访问 |
| `service.py` | 事务边界与业务编排 |
| `errors.py` | 模块错误 |

依赖方向为 `API → Service → Repository/Infrastructure`。Repository 之间不互调，Agent 只能依赖公开 Service。

## Agent 与工具边界

- `agents/dependencies.py` 在 FastAPI 请求范围内完成业务 Service、工具、注册表、执行器和 Agent 的依赖装配。
- `agents/tools/base.py` 定义模型可见的工具契约；`registry.py` 维护显式白名单；`executor.py` 统一处理参数校验、确认门禁、超时和安全错误。
- 具体工具按业务模块放在 `agents/tools/<module>/`，只依赖对应模块公开 Service，不接收 Session 或 Repository。
- `llm/contracts.py` 是 Provider 无关的文本、工具调用和流式增量契约；`llm/clients/` 只负责协议适配；`llm/orchestration/` 负责有限模型—工具循环。
- 新增工具时先补齐 Pydantic 输入/输出模型和 Service 权限校验，再在请求依赖中显式注册；不得通过目录扫描自动暴露工具。

## Chat 子包边界

Chat 按业务职责拆包，包内维护对应的 API、Schema、Service 和持久化实现。会话与消息归 `conversation/`，显式学习流程、Prompt、草稿和反馈归 `learning/`，固定上下文文件的读取、条件更新和视图转换归 `context/`，运行幂等与租约归 `runs/`；旧无状态问答归 `legacy/`。根 `api.py` 只聚合路由，`dependencies.py` 负责共享请求级 Session 的公开依赖装配，`_persistence.py` 仅保留 ID 字段类型及仓储基础操作。

这里的 `app/modules/chat/context/` 是后端代码职责目录，不代表 MinIO 中允许存在 `system/context/`。对象存储仍只使用第 19 篇约定的固定文件布局。

Model 和 Repository 分属会话、上下文、运行子包；学习没有独立业务表，使用同一请求内的上下文与会话仓储。跨表提交由 Service 控制，Repository 不互调、不自行提交。报告的 Schema 与依赖装配归 `report/`，文件解析通过 Chat 公开依赖获取运行服务。详细目录、事务和验收范围见 [Chat 模块分层设计](./26-Chat模块分层设计.md)。

有效上下文正文以 MinIO `system/` 固定文件为准；学习草稿、反馈和确认计划是 MySQL 工作流数据。上下文存储适配只封装固定对象的读取、ETag 条件覆盖和哈希校验，不创建 manifest 或版本目录。MySQL 保存会话、候选审核、来源变更、运行、游标和协调记录，所有 MinIO／模型调用都在数据库事务结束后进行。当前代码仍保留待迁移的 ContextStore，目标边界与恢复协议见 [云端上下文与显式学习改造](./27-云端上下文与显式学习改造.md)。

## Project Context 上下文产物边界

`app/project_context/` 负责文件详情、项目规范和项目索引等可重建上下文产物，不拥有业务表，也不承担数据库查询。项目记录、所有权、状态和生命周期编排仍归 `app/modules/project/`，文件事务、同步、上传和分析批次编排仍归 `app/modules/project_file/`。

- `file_detail/` 负责文件内容提取后的结构化详情构建，不负责文件事务、分析批次或数据库回填编排。
- `index/__init__.py` 只公开 `ProjectIndexDocument` 和 `ProjectIndexService`。
- `index/schemas.py` 定义与 `index.json` 对应的强类型 Pydantic 快照模型，不依赖 ORM、Repository 或业务状态枚举。
- `index/service.py` 负责根据调用方传入的项目和文件数据构建、初始化并发布 `system/index.json`；不得注入 Session、调用 Repository 或自行查询 MySQL。
- `specification/` 负责根据调用方提供的有效文件详情构建和发布项目规范，不负责查询项目文件。
- 项目、文件管理和文件解析 Service 负责查询权威数据、控制事务以及编排 `project_specification.json → index.json` 的发布顺序。`ProjectIndexService` 不调用项目规范 Service，两个上下文模块由业务 Service 协调。
- `index.json` 使用 `2.0.0` 协议，不暴露分析管线版本；`detail_ref` 为空表示当前文件尚无有效详情。

`app/llm/structured.py` 提供 Provider 无关的结构化 JSON 生成与 Pydantic 校验；`app/llm/prompts/project_context/` 存放文件详情、项目规范等上下文 Prompt，`app/llm/prompts/memory/` 存放尚未启用的记忆和用户习惯 Prompt。Prompt 包只描述模型输入约束，不依赖业务 Service、Repository 或存储设施。

`app/maintenance/` 只存放需要显式维护窗口执行的一次性命令，不接入 FastAPI 路由。`remove_analysis_version.py` 负责旧详情对象、项目规范引用和索引快照迁移；成功后才能执行对应 Alembic 删列迁移。

## Project File 子包边界

`project_file/` 根目录保留共享的 `ProjectFile` ORM、文件业务类型和状态枚举、`ProjectFileRepository`、路由聚合及公开 Service 导出。`pm_project_file` 仍只有一个持久化网关，两个子包不重复定义模型或跨 Repository 操作数据库。

- `management/` 负责用户源文件的上传、覆盖、路径修改、删除、列表、预签名地址、幂等控制、乐观锁和状态机；可以在 MinIO 中创建、读取、复制和删除源文件对象。
- `analysis/` 负责读取待分析源文件、执行内容提取和语义分析、写入 `system/file_details/*.json`、更新分析投影并触发项目规范和项目索引发布；不得上传、改名、覆盖或删除用户源文件。
- 两个子包不得互相导入 Service。跨模块协作只依赖 `ProjectService`、`ProjectIndexService` 等公开接口，共享持久化能力只依赖根目录的 Repository。
- MinIO 和 LLM 调用必须位于数据库事务之外，分析产物不是源文件管理接口的权威数据。

以下目录是本地留档资产，主业务完成前不得继续开发或重构：

- `archive/agent-service-deferred/eval/`
- `archive/agent-service-deferred/training/`
- `archive/agent-service-deferred/normalization_demo/`
- `archive/agent-service-deferred/examples/`
- `archive/agent-service-deferred/resources/`
- `archive/agent-service-deferred/scripts/`
- `project_test/`

归一化正式实现位于 `app.input_context.normalization`；`app.normalization` 仅保留公开符号和历史子模块路径的兼容门面，避免影响现有评测依赖。
