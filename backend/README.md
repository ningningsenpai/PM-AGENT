# PM-Agent Java 后端

当前 Java 模块是无租户隔离的多用户后端基座，保留公共能力、认证、当前用户资料，以及最小项目归属和MinIO文件管理。

## 技术基线

- Java 17、Spring Boot 3、Maven
- MyBatis Plus、MySQL 8、Flyway
- MinIO Java SDK
- Sa-Token + JWT
- Jakarta Validation、Hutool、MapStruct、Lombok
- Knife4j / OpenAPI 3
- SLF4J + Logback

## 当前范围

保留：

- 统一响应 `R<T>`；
- 统一错误码和全局异常处理；
- `X-Trace-Id` 生成、透传和 MDC 日志；
- 用户注册、邮箱登录和退出；
- 当前账户资料查询、修改和密码修改；
- 项目文件空间创建、初始 `system/index.json` 写入、查询和硬删除；
- 项目文件三次重试上传、同对象键覆盖、文件重命名迁移、只读地址和删除；
- 快速指纹、内容SHA-256、路径目录过滤、固定文件名过滤、扩展名黑白名单、内容MIME识别与文件失败状态；
- 内部健康检查。

不包含完整项目管理、任务、Agent、RabbitMQ、outbox、多租户、RBAC、文件历史版本和逻辑删除。

## 数据库

Flyway 创建 `pm_user`、最小 `pm_project` 和 `pm_project_file`，并通过后续迁移删除历史上传记录、明细表以及当前阶段未使用的成员和任务旧表。用户名和邮箱分别使用唯一索引，邮箱是登录标识。

迁移历史按增量方式保留，已执行过的 V1–V6 不直接改写，旧结构由后续迁移收敛。已有完整 `flyway_schema_history` 的数据库可以直接增量执行最新迁移；只有“数据库非空但缺少 Flyway 历史表”的开发库才需要在确认数据可丢弃后重建。

如果启动日志提示数据库非空但不存在 `flyway_schema_history`，不要启用 `baseline-on-migrate` 绕过检查。该状态无法证明现有表对应哪个迁移版本；开发环境应先备份需要的数据，再重建空数据库或 MySQL 数据卷，让 Flyway 完整执行 V1–V7。

## 本地启动

```bash
mvn spring-boot:run
```

默认端口为 `8080`，数据库连接读取：

- `PM_AGENT_DB_USERNAME`，默认 `pm_agent`
- `PM_AGENT_DB_PASSWORD`，默认 `pm_agent_dev`
- `PM_AGENT_JWT_SECRET`，生产环境必须显式配置
- `MINIO_ENDPOINT`，默认 `http://localhost:9000`
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
- MinIO Bucket 固定为 `pm-agent`

## 验证命令

```bash
mvn clean test
mvn package
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/internal/health` | 健康检查 |
| `POST` | `/api/v1/auth/register` | 注册用户 |
| `POST` | `/api/v1/auth/login` | 邮箱登录 |
| `POST` | `/api/v1/auth/logout` | 退出 |
| `GET` | `/api/v1/users/me` | 查询当前账户资料 |
| `PUT` | `/api/v1/users/me` | 修改当前账户资料 |
| `PUT` | `/api/v1/users/me/password` | 修改当前账户密码 |
| `POST` | `/api/v1/projects` | 创建项目文件空间并初始化索引 |
| `GET` | `/api/v1/projects` | 查询项目文件空间 |
| `DELETE` | `/api/v1/projects/{projectId}` | 硬删除项目及根前缀全部对象 |
| `POST` | `/api/v1/projects/{projectId}/files` | 上传单个文件 |
| `PUT` | `/api/v1/projects/{projectId}/files/{fileId}/content` | 覆盖文件内容 |
| `PATCH` | `/api/v1/projects/{projectId}/files/{fileId}/path` | 修改逻辑路径 |
| `GET` | `/api/v1/projects/{projectId}/files` | 查询项目文件 |
| `GET` | `/api/v1/projects/{projectId}/files/{fileId}/read-url` | 获取临时只读地址 |
| `DELETE` | `/api/v1/projects/{projectId}/files/{fileId}` | 删除文件 |

Knife4j 入口：`/doc.html`。

详细设计见：

- [`docs/04-数据模型.md`](../docs/04-数据模型.md)
- [`docs/05-接口规范.md`](../docs/05-接口规范.md)
- [`docs/13-用户认证模块设计.md`](../docs/13-用户认证模块设计.md)
