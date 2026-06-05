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
- MyBatis Plus；
- Sa-Token + JWT；
- MySQL 8；
- Jakarta Validation；
- Hutool + MapStruct；
- 包名根：`com.ning.pm.<module>`。

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-backend-architect/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
