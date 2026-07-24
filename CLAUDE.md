# CLAUDE.md

本仓库的协作规则、架构边界、受保护目录和常用命令统一维护在 [AGENTS.md](./AGENTS.md)。

当前运行链路为：

```text
Vue 3 → FastAPI 模块化单体 → MySQL / Redis / MinIO / LLM
```

Python 是业务表唯一写入者，Alembic 是唯一 Schema 所有者。历史文档中的 Java、Sa-Token、MyBatis Plus、Flyway 和 Java/Python HTTP 自调用描述已失效，以 [Python 单体后端迁移说明](./docs/21-Python单体后端迁移说明.md) 为准。
