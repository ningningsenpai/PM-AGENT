# PM-Agent 前端工程

本目录用于存放 PM-Agent 的 Vue 3 前端代码，是 PM-Agent 单仓库 Monorepo 的前端模块。

## 仓库与分支说明

项目采用 **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支**：

- `main` 分支：维护完整项目基线，包含文档、前端、后端、部署配置和后续 Agent 服务骨架；
- `frontend/` 目录：维护前端工程代码，不再对应长期 `frontend` 模块分支；
- 前端相关任务使用 `feature/*` 分支开发，例如 `feature/init-frontend`、`feature/auth-login`；
- 前后端联调功能可以在同一个任务分支内同时修改 `frontend/`、`backend/` 和 `docs/`。

详细规则见 `docs/12-Git管理策略.md`。

## 技术基线

前端开发应遵守：

- Vue 3；
- TypeScript；
- Vite；
- Node.js 20 LTS；
- pnpm；
- Naive UI；
- Pinia；
- Vue Router；
- ECharts；
- Axios；
- UnoCSS 可选，不与 Tailwind 同时引入。

## 本地启动

当前环境要求：

```bash
node --version # 期望为 20.x
pnpm --version # 期望为 9.x 或更高
```

初始化依赖并启动：

```bash
pnpm install
cp .env.example .env
pnpm dev
```

如本机尚未安装 pnpm，可先启用 Corepack：

```bash
corepack enable
corepack prepare pnpm@9.15.4 --activate
```

## 第 1 阶段开发约定

- 前端代码统一放在 `frontend/` 目录；
- 后端代码统一放在 `backend/` 目录，后续从 `main` 新建 `feature/init-backend` 初始化；
- 第 1 阶段前端开发期提供简单本地 Mock 层，接口未完成前模拟登录、项目和任务数据；
- 任务看板第 1 阶段使用下拉框切换任务状态，拖拽能力后置到后续阶段。

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-frontend-builder/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
- `docs/12-Git管理策略.md`
