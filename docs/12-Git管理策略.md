# Git 管理策略

## 1. 背景

PM-Agent 当前采用前端、后端、Python Agent 服务与部署配置共存在同一仓库的开发方式。早期曾考虑使用 `frontend`、`backend` 等长期分支区分模块，但这种方式会导致文档、部署配置、接口约定和前后端联调状态在多个分支之间反复同步。

为降低单人 + AI 协作开发的管理成本，后续统一采用：

> **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支。**

---

## 2. 目标

1. 让 `main` 始终代表 PM-Agent 的完整项目基线；
2. 用目录区分前端、后端、Agent 服务和部署配置；
3. 用分支区分一次开发任务、功能闭环或修复事项；
4. 支持前后端联调功能在同一个任务分支内完成；
5. 减少文档、Skill、部署配置在长期模块分支之间反复合并。

---

## 3. 仓库结构原则

项目继续采用单仓库结构：

```text
PM-AGENT/
├── frontend/        # Vue 3 前端工程
├── backend/         # Spring Boot 后端工程
├── agent-service/   # Python Agent 服务，按阶段引入
├── deploy/          # 本地中间件与部署配置
├── docs/            # 项目文档
├── .claude/         # Claude Code 项目级配置与 Skill
└── CLAUDE.md        # 项目协作说明
```

核心原则：

- **目录区分模块**：例如前端代码放在 `frontend/`，后端代码放在 `backend/`；
- **分支区分任务**：例如登录闭环、项目接口、任务看板等；
- **文档和部署配置跟随任务更新**：如果一个功能同时影响接口、页面和部署配置，应在同一个任务分支内同步修改。

---

## 4. 分支模型

### 4.1 主干分支

| 分支 | 职责 |
|---|---|
| `main` | 完整项目基线，包含文档、前端、后端、部署配置和后续 Agent 服务骨架 |

`main` 不用于长期只维护某一个模块。任何进入 `main` 的提交都应尽量保持项目结构清晰、文档口径一致。

### 4.2 任务分支

推荐分支命名：

```text
feature/init-frontend
feature/init-backend
feature/auth-login
feature/project-management
feature/task-kanban
fix/token-expire
chore/docker-middleware
docs/git-strategy
```

不再推荐使用以下长期模块分支：

```text
frontend
backend
agent-service
```

如果当前本地仍处于 `frontend` 分支，可将其视为历史上的前端初始化任务分支，并在整理后改名为：

```text
feature/init-frontend
```

---

## 5. 开发与合并规则

### 5.1 新功能开发

1. 从 `main` 拉出任务分支；
2. 在任务分支中完成相关目录改动；
3. 如涉及接口、数据模型、部署或验收标准，同步更新 `docs/`；
4. 自测通过后合并回 `main`。

示例：

```bash
git switch main
git pull
git switch -c feature/auth-login
```

### 5.2 前后端联调

登录、项目管理、任务看板等功能可以在同一个任务分支内同时修改：

```text
feature/auth-login
├── frontend/
├── backend/
└── docs/
```

这类分支不需要拆成前端分支和后端分支。拆分只在任务规模过大、无法一次闭环时进行。

### 5.3 提交规范

提交信息继续采用 Conventional Commits，并建议使用 scope 标明影响模块：

```text
feat(frontend): 初始化 Vue 3 前端工程
feat(backend): 初始化 Spring Boot 后端工程
feat(auth): 完成登录接口与前端联调
docs(git): 更新 Git 管理策略
chore(deploy): 添加 MySQL 本地容器配置
```

---

## 6. 当前整理建议

当前整理目标不是拆仓库，而是统一 Git 语义：

1. 保留单仓库；
2. 让 `main` 作为完整项目主线；
3. 将当前 `frontend` 分支视为 `feature/init-frontend`；
4. 前端初始化、部署配置和本轮文档整理完成后合并回 `main`；
5. 后续后端工程从 `main` 新建 `feature/init-backend`；
6. 不再新增长期 `backend` 分支。

---

## 7. 验收标准

- `main` 的定位明确为完整项目基线；
- 文档中不再把 `frontend` / `backend` 描述为长期模块分支；
- `frontend/README.md` 说明前端目录职责，而不是说明长期前端分支职责；
- 第 1 阶段后端初始化分支命名调整为 `feature/init-backend`；
- 后续功能分支按任务或功能闭环命名。

---

## 8. 待确认问题

暂无。
