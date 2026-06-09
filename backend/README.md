# PM-Agent 后端工程

本目录用于存放 PM-Agent 的 Java Spring Boot 后端代码，是 PM-Agent 单仓库 Monorepo 的后端模块。

## 仓库与分支说明

项目采用 **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支**：

- `main` 分支：维护完整项目基线，包含文档、前端、后端、部署配置和后续 Agent 服务骨架；
- `backend/` 目录：维护 Java Spring Boot 后端代码，不再对应长期 `backend` 模块分支；
- 后端相关任务使用 `feature/*` 分支开发，例如 `feature/auth-login`、`feature/project-api`；
- 前后端联调功能可以在同一个任务分支内同时修改 `frontend/`、`backend/` 和 `docs/`。

详细规则见 `docs/12-Git管理策略.md`。

## 技术基线

后端开发应遵守：

- Spring Boot 3；
- Java 17+；
- Maven；
- MyBatis Plus；
- Sa-Token + JWT；
- MySQL 8；
- Flyway；
- Jakarta Validation；
- Hutool + MapStruct；
- 包名根：`com.ning.pm.<module>`。

## 本地启动

第 1 阶段后端连接本地 Docker MySQL，数据库表结构由 Flyway 自动迁移。

```bash
mvn spring-boot:run
```

健康检查：

```text
GET /internal/health
```

接口文档入口：

```text
/doc.html
```

## 当前已初始化能力

- Maven + Spring Boot 3 工程；
- 统一响应 `R<T>`；
- 错误码 `ErrorCode`；
- 基础异常体系与全局异常处理；
- traceId 拦截器；
- 写接口幂等键校验拦截器；
- MyBatis Plus 基础配置与自动填充；
- Sa-Token JWT 登录态；
- Knife4j / OpenAPI 基础配置；
- Flyway 第 1 阶段建表脚本；
- Flyway 演示数据初始化脚本；
- 用户注册、登录、登出和当前用户接口；
- 审计日志占位注解与空切面。

## 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/internal/health` | 健康检查 |
| `POST` | `/api/v1/auth/register` | 注册用户并返回登录态 |
| `POST` | `/api/v1/auth/login` | 用户登录 |
| `POST` | `/api/v1/auth/logout` | 用户登出 |
| `GET` | `/api/v1/users/me` | 查询当前登录用户资料 |

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-backend-architect/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
- `docs/13-用户认证模块设计.md`
