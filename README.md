# PM-AGENT

PM-Agent 是一个基于 Java + Python + 大模型 Agent 的智能项目管理平台，面向项目经理、研发团队与管理层，支持项目、需求、任务、迭代、风险、报告等结构化管理，并逐步引入 Agent 分析、周报生成、风险识别和 RAG 知识检索能力。

## 仓库结构

本仓库采用单仓库 Monorepo 管理方式：

```text
PM-AGENT/
├── frontend/        # Vue 3 前端工程
├── backend/         # Spring Boot 后端工程，待初始化
├── agent-service/   # Python Agent 服务，第 3 阶段引入
├── deploy/          # 本地中间件与部署配置
├── docs/            # 项目文档
├── .claude/         # Claude Code 项目级配置与 Skill
└── CLAUDE.md        # 项目协作说明
```

## Git 管理策略

项目统一采用：

> **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支。**

- `main` 代表完整项目基线；
- 目录负责区分前端、后端、Agent 服务和部署配置；
- 分支负责区分开发任务或功能闭环；
- 不再使用长期 `frontend` / `backend` 分支表示模块；
- 详细规则见 [docs/12-Git管理策略.md](./docs/12-Git管理策略.md)。

## 当前阶段

当前处于第 1 阶段：项目基础骨架与 MVP 前置能力。

- 已初始化：项目文档、项目级 Skill、前端工程、本地 MySQL 中间件配置；
- 待初始化：`backend/` Spring Boot 3 + Maven 后端工程；
- 后续：从 `main` 创建 `feature/init-backend`，落地用户、项目、任务最小闭环。

## 文档入口

- [docs/README.md](./docs/README.md)：项目文档索引；
- [CLAUDE.md](./CLAUDE.md)：项目协作规范；
- [docs/01-开发规划.md](./docs/01-开发规划.md)：分阶段开发规划；
- [docs/12-Git管理策略.md](./docs/12-Git管理策略.md)：Git 分支与合并规则。
