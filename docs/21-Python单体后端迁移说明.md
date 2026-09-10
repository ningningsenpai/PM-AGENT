# Python 单体后端迁移说明

## 决策

PM-Agent 在线后端全量迁移至 `agent-service/`，采用 FastAPI 模块化单体。迁移完成后不保留 Java 运行时。

这份文档是运行架构迁移的最新基线；历史文档中关于 Spring Boot、Sa-Token、MyBatis Plus、Flyway、Java/Python HTTP 自调用和 Java 工具 API 的描述均已失效。

## 收敛原则

- Python 是业务表唯一写入者。
- Alembic 是唯一数据库迁移所有者。
- 应用启动时校验数据库 Alembic revision；数据库落后或版本未知时拒绝进入就绪状态，并输出中文迁移提示。
- Agent 与业务模块同进程，但继续通过公开 Service 隔离。
- 文件解析直接使用 MinIO SDK，不使用预签名 URL 做内部下载。
- 外部存储和模型调用不占用数据库事务。
- MySQL 会话固定使用 `+08:00`，业务时间统一按 `Asia/Shanghai` 写入和输出。
- 保留 `agent-service/` 目录名；延期 Agent 资产统一放入本地留档区。
- 不迁移历史数据，不建设双写或灰度双运行。

## 受保护资产

迁移不得修改：

- `archive/agent-service-deferred/eval/**`
- `archive/agent-service-deferred/training/**`
- `archive/agent-service-deferred/normalization_demo/**`
- `archive/agent-service-deferred/examples/**`
- `archive/agent-service-deferred/resources/**`
- `archive/agent-service-deferred/scripts/**`
- `agent-service/project_test/**`

`app.normalization` 保持公共符号兼容。

## 验收

- 分支为 `feature/migrate`；
- Python 契约测试、Alembic DDL、前端类型检查和构建通过；
- 认证、项目、文件上传、解析和 Agent 路由均由 FastAPI 提供；
- Java 后端目录移除；
- 受保护目录相对 `main` 零差异；
- 不推送远程分支，不创建 PR。
