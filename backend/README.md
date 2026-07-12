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
- 最小项目文件空间创建与查询；
- 项目文件上传、同对象键覆盖、路径修改、只读地址和删除；
- 快速指纹、内容SHA-256、上传批次与失败状态；
- 内部健康检查。

不包含完整项目管理、任务、Agent、RabbitMQ、outbox、多租户、RBAC、文件历史版本和逻辑删除。

## 数据库

Flyway创建`pm_user`、最小`pm_project`、项目文件和上传追踪表。用户名和邮箱分别使用唯一索引，邮箱是登录标识。

本次迁移历史已经重写。已有本地数据库必须在确认不再需要旧数据后重置，再启动后端执行新的 `V1__init_phase1_schema.sql`。

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
- `MINIO_BUCKET`，默认 `pm-agent`

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
| `POST` | `/api/v1/projects` | 创建项目文件空间 |
| `GET` | `/api/v1/projects` | 查询项目文件空间 |
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
