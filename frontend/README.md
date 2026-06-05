# PM-Agent 前端工程

本目录用于存放 PM-Agent 的 Vue 3 前端代码。

## 分支说明

当前目录属于长期分支：`frontend`。

- `main` 分支：维护项目文档、正式 Skill、中文参考 Skill；
- `frontend` 分支：在继承 `main` 文档与 Skill 的基础上，维护前端代码；
- 后续如 `main` 更新文档或 Skill，可将 `main` 合并到 `frontend` 同步。

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

- 当前 `frontend` 分支只维护前端代码；
- 后端代码另建 `backend` 分支维护；
- 前端开发期提供简单本地 Mock 层，接口未完成前模拟登录、项目和任务数据；
- 任务看板第 1 阶段使用下拉框切换任务状态，拖拽能力后置到后续阶段。

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-frontend-builder/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
