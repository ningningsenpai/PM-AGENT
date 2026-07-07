---
name: pm-agent-frontend-builder
description: Frontend development skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user designs Vue 3 frontend architecture, page structure, visual systems, Figma prototypes, component boundaries, routing, Pinia state, Naive UI tables/forms, project kanban, Agent chat pages, data visualization, or frontend implementation plans. It should preserve the confirmed PM-Agent Warm Linear visual direction.
metadata:
  status: active
  language: en-US
  owner_module: frontend
  related_docs:
    - docs/01-开发规划.md
    - docs/03-业务流程.md
    - docs/05-接口规范.md
---

# PM-Agent Frontend Development Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing or implementing a Vue 3 + TypeScript frontend project structure;
- Designing pages, routes, layouts, navigation, tables, forms, detail pages, or kanban pages;
- Designing Agent chat pages, tool-call process display, Trace display, or weekly-report generation interactions;
- Designing frontend API wrappers, state management, permission routes, and error prompts;
- Reviewing whether frontend changes match PM-Agent’s product style and phase plan.

## Goal

Help Codex produce readable frontend plans with clear component boundaries and a mature visual result for PM-Agent. The default base is an admin system, but it should avoid becoming a dull table-only interface. It should reflect Linear-style simplicity, whitespace, hierarchy, and state clarity.

---

## 1. Technical baseline

| Item | Choice | Notes |
|---|---|---|
| Framework | Vue 3 | Do not use React |
| Language | TypeScript | Prefer strong typing |
| Build | Vite | |
| Component library | Naive UI | Primary style system |
| State management | Pinia | |
| Routing | Vue Router | |
| Charts | ECharts | Dashboards and trends |
| HTTP | Axios | Unified interceptor wrapper |
| Style enhancement | UnoCSS optional | Atomic styles allowed; do not introduce Tailwind at the same time |

Ask the user before replacing locked choices such as Naive UI, Vue 3, Pinia, or Axios.

---

## 2. Visual and interaction style

PM-Agent has a confirmed visual direction: **Warm Linear workspace style**. Treat it as the default design language for frontend pages and Figma prototypes unless the user explicitly changes it.

### 2.1 Core direction

1. Default to a **Warm Linear style**: Linear-inspired simplicity, whitespace, clear hierarchy, low-saturation status colors, compact but not crowded, with warmer blue/green/yellow/white tones.
2. The product should feel like a project execution workspace, not a generic admin dashboard. Express traceability, state flow, and Agent insight through layout and visual motifs.
3. Do not consider dark mode for now; do not complicate the theme system early for dark mode.
4. Do not optimize for mobile in the first version; prioritize desktop admin experience.
5. Admin systems are not only tables. Use cards, statistic blocks, risk tags, timelines, kanban columns, insight cards, and status colors to increase information density.
6. Agent pages should emphasize chat, tool-call steps, referenced data, executable actions, and human-confirmation results.
7. Use motion only for state feedback, not decorative flourish.

### 2.2 Confirmed color system

Use blue, green, yellow, and white as the base palette. Keep the approximate visual ratio: warm white/background 65%, blue 20%, green 10%, yellow 5%.

| Token | Suggested value | Use |
|---|---|---|
| PM Blue | `#2F7DF6` / `#1F66D1` | Primary actions, links, project progress, selected navigation |
| PM Green | `#26B983` / `#15966A` | Healthy status, completed state, positive progress |
| PM Yellow | `#F5B83D` / `#D8911E` | Agent insights, risk hints, focus highlights |
| Warm White | `#F8FAF5` / `#FFFFFF` | Page background, cards, content surfaces |
| Main Text | `#132033` | Primary titles and important values |
| Secondary Text | `#667085` | Descriptions, metadata, supporting text |
| Muted Text | `#98A2B3` | Empty states, hints, low-priority details |

Do not spread yellow evenly across the UI. Yellow means “insight / something worth attention”, especially Agent suggestions or risk clues.

### 2.3 Brand and visual motifs

1. Use the brand idea **“turn project status into traceable execution clues.”**
2. The logo direction uses a dark rounded mark, blue execution orbit, green status node, yellow insight node, and a Trace-like connection line. Keep this logic when refining the brand.
3. Reuse the “execution clue line” motif in cards and layouts: slim left border, top progress strip, connected dots, or timeline markers.
4. Backgrounds may use a warm morning-light atmosphere: off-white base, soft blue glow, soft green glow, and small yellow insight glow. Avoid heavy gradients or purple AI-style visuals.

### 2.4 Layout rules

1. Main app layout should preserve: left navigation + top status bar + content workspace.
2. Project workspace should favor: page header, metric cards, project cards, kanban preview, and Agent insight reservation area.
3. Business detail pages should favor: summary area + tabs + main work area + right-side execution clue/insight panel.
4. Auth pages can be bolder than internal pages: large brand hero, execution path visual, glass login/register cards.
5. Reserve future entries for risk, Agent, report, and Trace, but do not implement later-stage business logic early.

### 2.5 Typography and component sizing

Prefer product-tool fonts such as `MiSans`, `HarmonyOS Sans SC`, or `Microsoft YaHei` in implementation. If unavailable in Figma, use `Inter` for prototypes. Avoid using `LXGW WenKai Screen` globally; it may be used only for occasional brand accents if the user wants a more expressive hero.

| Element | Size | Weight |
|---|---:|---:|
| Page title | 28–32px | 700–800 |
| Hero title | 52–64px | 800 |
| Card title | 18–22px | 650–700 |
| Body text | 14px | 400 |
| Supporting text | 12–13px | 400–500 |
| Metric number | 28–40px | 700–800 |

Radii and spacing:

- Page/card large radius: 24–30px;
- Normal card radius: 18–24px;
- Button/input radius: 10–14px;
- Tag radius: `999px`;
- Use 4px-based spacing: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.

### 2.6 Confirmed prototype pages

The current Figma prototype direction includes these baseline screens:

1. Brand foundation: logo, color palette, type/component examples;
2. Auth screens: login and register with a stronger brand hero;
3. Project workspace: sidebar, top bar, metrics, project cards, kanban preview, Agent insight placeholder;
4. Business layout: project summary, tabs, task kanban, right-side execution clue panel.

When implementing frontend code, keep these structural decisions stable to avoid frequent layout rework.

---

## 3. Directory structure

Organize by **business module → pages/components**. Avoid scattering business logic by generic component type.

```text
frontend/src
├── app                 App initialization and global providers
├── router              Route config and permission guards
├── stores              Global Pinia state
├── api                 Axios instance and module APIs
├── shared              Shared components, hooks, utilities, types
├── layouts             Main layout and login layout
└── modules
    ├── project
    │   ├── pages
    │   ├── components
    │   ├── api.ts
    │   ├── types.ts
    │   └── store.ts
    ├── task
    ├── requirement
    ├── risk
    └── agent
```

### Naming conventions

| Type | Convention | Example |
|---|---|---|
| Vue component | PascalCase | `TaskBoard.vue` |
| File/directory | kebab-case or lowercase business name | `task-card.vue` / `modules/task` |
| API function | Verb + resource | `createTask`, `listProjects` |
| Type | PascalCase | `TaskDetailResponse` |
| Store | `useXxxStore` | `useTaskStore` |

---

## 4. API and request wrapper

1. All business APIs use the `/api/v1/` prefix.
2. Axios must be wrapped with unified request/response interceptors.
3. Request headers:
   - `Authorization`: attached automatically after login;
   - `X-Trace-Id`: frontend may generate and pass through; backend has fallback;
   - `X-Idempotency-Key`: required for all write APIs; generate per form or action and reuse on retry.
4. Unified response structure follows the backend skill: `code/message/data/traceId`.
5. Non-zero error codes should show Chinese error prompts, while retaining traceId in debug information.
6. Do not scatter `axios.get/post` calls. Encapsulate them through `modules/<module>/api.ts` or `api/<module>.ts`.

---

## 5. Page design principles

### 5.1 Project and task pages

- Phase 1 must display project list, project detail, and task list/kanban.
- The first task-kanban version does **not** require drag and drop. Use status-grouped columns first.
- If drag and drop is added later, confirm state transition rules and backend API idempotency first.

### 5.2 Agent page

The Agent page is not just a chat box. Reserve at least four areas:

1. User input and model output;
2. Agent tool-call process: tool name, input summary, result summary, duration, status;
3. Referenced project/task/risk data;
4. Action cards requiring human confirmation.

### 5.3 Forms and feedback

- Use Naive UI validation. Error prompts must be Chinese.
- Save, delete, Agent execution, and other writes must have loading states and duplicate-submit prevention.
- High-risk operations must use a second confirmation. Button color alone is not enough to communicate risk.

---

## 6. Frontend plan output format

When designing a page or module, output this structure:

```markdown
# 前端方案：[页面/模块名称]

## 页面目标
## 目标用户与使用场景
## 路由与页面结构
## 组件拆分
## 状态管理
## API 依赖
## 请求头与幂等处理
## 交互细节
## 视觉设计建议
## 异常与空状态
## 开发步骤
## 验收标准
## 待确认问题
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 7. Workflow

1. Confirm which development phase the page belongs to, avoiding early implementation of later capabilities.
2. Check the product glossary so page copy, component names, and route names stay consistent.
3. Design the user journey before splitting components and state.
4. Clarify API dependencies and mark whether the backend already exists.
5. Prefer Naive UI components; use UnoCSS only for layout refinements when needed.
6. Acceptance criteria must include a manual operation path.

---

## 8. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Replacing Vue 3, Naive UI, Pinia, or Axios;
- Introducing both Tailwind and UnoCSS;
- Forcing task-kanban drag and drop in the first version;
- Introducing full dark mode or mobile adaptation;
- Bypassing the unified Axios wrapper for direct requests;
- Omitting confirmation dialogs for high-risk operations;
- Using new business terms not present in the glossary.
