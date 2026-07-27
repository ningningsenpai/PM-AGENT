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
├── modules/
│   ├── auth/
│   ├── user/
│   ├── project/
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
└── agents、llm、memory、normalization、project/context、rag
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

## Project File 子包边界

`project_file/` 根目录保留共享的 `ProjectFile` ORM、文件业务类型和状态枚举、`ProjectFileRepository`、路由聚合及公开 Service 导出。`pm_project_file` 仍只有一个持久化网关，两个子包不重复定义模型或跨 Repository 操作数据库。

- `management/` 负责用户源文件的上传、覆盖、路径修改、删除、列表、预签名地址、幂等控制、乐观锁和状态机；可以在 MinIO 中创建、读取、复制和删除源文件对象。
- `analysis/` 负责读取待解析源文件、调用文件分析器、写入 `system/file_details/*.json`、更新分析投影并触发项目索引重建；不得上传、改名、覆盖或删除用户源文件。
- 两个子包不得互相导入 Service。跨模块协作只依赖 `ProjectService`、`ProjectIndexService` 等公开接口，共享持久化能力只依赖根目录的 Repository。
- MinIO 和 LLM 调用必须位于数据库事务之外，分析产物不是源文件管理接口的权威数据。

以下目录是独立资产，在线业务迁移不得统一移动或重构：

- `eval/`
- `training/`
- `normalization_demo/`
- `project_test/`
- `examples/`

`app.normalization` 的公开符号保持兼容，避免影响现有评测依赖。
