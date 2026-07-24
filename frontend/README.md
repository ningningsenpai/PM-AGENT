# PM-Agent 前端工程

本目录用于存放 PM-Agent 的 Vue 3 前端代码，是 PM-Agent 单仓库 Monorepo 的前端模块。

## 仓库与分支说明

项目采用 **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支**：

- `main` 分支：维护完整项目基线，包含文档、前端、后端、部署配置和后续 Agent 服务骨架；
- `frontend/` 目录：维护前端工程代码，不再对应长期 `frontend` 模块分支；
- 前端相关任务使用 `feature/*` 分支开发，例如 `feature/init-frontend`、`feature/auth-login`；
- 前后端联调功能可以在同一个任务分支内同时修改 `frontend/`、`agent-service/` 和 `docs/`。

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

## 页面结构

当前前端按“公开入口 + 认证页 + 受保护工作台”组织：

```text
/
├── 项目介绍页，公开访问
├── /login        登录页，公开访问
├── /register     注册页，公开访问
└── /projects     项目工作台，需登录
    ├── /projects/:id
    └── /projects/:id/tasks
```

路由定义位于 `src/router/index.ts`。受保护页面会检查本地 `pm-agent-token`，必要时调用 `/api/v1/users/me` 恢复当前用户。

## 目录约定

前端代码按“业务模块 → 页面 / 组件 / API / 类型”组织：

```text
src
├── api                 # Axios 实例与统一 request<T>()
├── layouts             # 主应用布局
├── modules
│   ├── auth            # 登录、注册、认证接口与认证组件
│   ├── landing         # 项目介绍等公开页面
│   ├── project         # 项目页面、接口、状态
│   └── task            # 任务页面、接口、状态
├── router              # 路由与登录守卫
├── shared              # 全局样式、工具、通用类型
└── stores              # 全局 Pinia Store
```

业务请求不得在页面中直接调用 `axios.get/post`，应通过：

1. `src/api/http.ts` 的 `request<T>()`；
2. `src/modules/<module>/api.ts` 的模块 API 函数。

## 认证接口契约

后端统一返回结构：

```json
{
  "code": 0,
  "message": "成功",
  "data": {},
  "traceId": "abc123"
}
```

认证相关接口：

| 功能 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 注册 | POST | `/api/v1/auth/register` | 返回 `tokenName/tokenValue/user` |
| 登录 | POST | `/api/v1/auth/login` | 返回 `tokenName/tokenValue/user` |
| 登出 | POST | `/api/v1/auth/logout` | 退出当前登录态 |
| 当前用户 | GET | `/api/v1/users/me` | 返回当前用户资料 |

所有请求会自动携带 `X-Trace-Id`。登录后，请求会自动携带：

```http
Authorization: Bearer <tokenValue>
```

## Mock 与真实接口切换

`.env` 中通过以下变量控制：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK=true
```

- `VITE_USE_MOCK=true`：使用本地 Mock 数据，便于纯前端演示；
- `VITE_USE_MOCK=false`：请求真实后端接口；
- `VITE_API_BASE_URL`：真实后端地址，开发期默认可使用 `http://localhost:8000`。

## 第 1 阶段开发约定

- 前端代码统一放在 `frontend/` 目录；
- 第 1 阶段前端提供项目介绍、登录、注册、项目列表、项目详情和任务看板基础闭环；
- 任务看板第 1 阶段使用下拉框切换任务状态，拖拽能力后置到后续阶段；
- 风险中心、Agent 对话、周报、Trace 详情等页面在用户完善需求文档后再继续设计与开发。

详细规则见：

- `CLAUDE.md`
- `.claude/skills/pm-agent-frontend-builder/SKILL.md`
- `docs/02-技术选型.md`
- `docs/05-接口规范.md`
- `docs/12-Git管理策略.md`

## 验证命令

```bash
pnpm typecheck
pnpm build
```

`pnpm build` 会先执行 `vue-tsc --noEmit`，再执行 Vite 构建。
