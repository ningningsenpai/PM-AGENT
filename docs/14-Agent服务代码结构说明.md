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
└── agents、llm、memory、normalization、project/context、rag
```

每个在线业务模块采用垂直分层：

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

以下目录是独立资产，在线业务迁移不得统一移动或重构：

- `eval/`
- `training/`
- `normalization_demo/`
- `project_test/`
- `examples/`

`app.normalization` 的公开符号保持兼容，避免影响现有评测依赖。
