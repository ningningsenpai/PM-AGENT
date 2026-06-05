# PM-Agent 后端工程

本目录用于存放 PM-Agent 的 Java Spring Boot 后端代码。

## 分支说明

当前目录属于长期分支：`backend`。

- `main` 分支：维护项目文档、正式 Skill、中文参考 Skill；
- `backend` 分支：在继承 `main` 文档与 Skill 的基础上，维护后端代码；
- 后续如 `main` 更新文档或 Skill，可将 `main` 合并到 `backend` 同步。

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
- 基础异常体系；
- 全局异常处理；
- traceId 拦截器；
- 写接口幂等键校验拦截器；
- MyBatis Plus 基础配置；
- Flyway 第 1 阶段建表脚本；
- Flyway 演示数据初始化脚本；
- 审计日志占位注解与空切面。

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-backend-architect/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
