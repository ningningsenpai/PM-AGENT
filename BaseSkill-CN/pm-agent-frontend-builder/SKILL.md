---
name: pm-agent-frontend-builder
description: 面向 PM-Agent 智能项目管理 Agent 平台的前端开发 Skill。每当用户设计 Vue 3 前端架构、页面结构、组件拆分、路由、Pinia 状态、Naive UI 表格表单、项目看板、Agent 对话页、数据可视化或前端开发计划时，都应使用本 Skill。
metadata:
  status: active
  language: zh-CN
  owner_module: frontend
  related_docs:
    - docs/01-开发规划.md
    - docs/03-业务流程.md
    - docs/05-接口规范.md
---

# PM-Agent 前端开发 Skill

## 触发场景

当用户提出以下类型请求时使用本 Skill：

- 设计或实现 Vue 3 + TypeScript 前端工程结构；
- 设计页面、路由、布局、导航、表格、表单、详情页、看板页；
- 设计 Agent 对话页、工具调用过程展示、Trace 展示、周报生成交互；
- 设计前端 API 封装、状态管理、权限路由、错误提示；
- 评审前端改动是否符合 PM-Agent 的产品风格和阶段规划。

## 目标

帮助 Claude 为 PM-Agent 输出可读性强、组件边界清晰、视觉效果成熟的前端方案。默认以后台管理系统为基底，但避免做成单调表格页，要体现 Linear 风格的简洁、留白、层级和状态感。

---

## 一、技术基线

| 项 | 选型 | 备注 |
|---|---|---|
| 框架 | Vue 3 | 不使用 React |
| 语言 | TypeScript | 强类型优先 |
| 构建 | Vite | |
| 组件库 | Naive UI | 主样式系统 |
| 状态管理 | Pinia | |
| 路由 | Vue Router | |
| 图表 | ECharts | 数据看板与趋势图 |
| HTTP | Axios | 统一封装拦截器 |
| 样式增强 | UnoCSS 可选 | 接受原子化样式；不同时引入 Tailwind |

> 若要替换 Naive UI、Vue 3、Pinia、Axios 等已锁定选型，必须先询问用户。

---

## 二、视觉与交互风格

1. 默认采用 **Linear 风**：简洁、轻量、清晰层级、低饱和状态色、紧凑但不拥挤；
2. 暂不考虑深色模式；不要为了深色模式提前复杂化主题系统；
3. 不做移动端适配，优先桌面端后台管理体验；
4. 管理后台不等于纯表格：使用卡片、统计块、风险标签、时间线、状态色增强信息密度；
5. Agent 页面要突出：对话、工具调用步骤、引用数据、可执行动作、人工确认结果；
6. 动效仅用于状态反馈，不做花哨装饰。

---

## 三、目录结构

按 **业务模块 → 页面/组件** 组织，避免按组件类型把业务打散。

```text
frontend/src
├── app                 应用初始化、全局 provider
├── router              路由配置、权限守卫
├── stores              Pinia 全局状态
├── api                 Axios 实例、模块 API
├── shared              通用组件、hooks、工具、类型
├── layouts             主布局、登录布局
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

### 命名约定

| 类型 | 约定 | 示例 |
|---|---|---|
| Vue 组件 | PascalCase | `TaskBoard.vue` |
| 文件/目录 | kebab-case 或业务名小写 | `task-card.vue` / `modules/task` |
| API 函数 | 动词 + 资源 | `createTask`、`listProjects` |
| 类型 | PascalCase | `TaskDetailResponse` |
| Store | `useXxxStore` | `useTaskStore` |

---

## 四、API 与请求封装

1. 所有业务接口走 `/api/v1/` 前缀；
2. Axios 必须统一封装请求/响应拦截器；
3. 请求头规则：
   - `Authorization`：登录后自动携带；
   - `X-Trace-Id`：前端可生成并透传，后端兜底；
   - `X-Idempotency-Key`：所有写接口必须携带，由表单或动作级别生成并在重试时复用；
4. 统一响应结构按后端 Skill：`code/message/data/traceId`；
5. 非 0 错误码统一弹出中文错误提示，并在调试信息中保留 traceId；
6. 前端不要散落 `axios.get/post`，必须通过 `modules/<module>/api.ts` 或 `api/<module>.ts` 封装。

---

## 五、页面设计原则

### 5.1 项目与任务页

- 第 1 阶段必须能展示项目列表、项目详情、任务列表/看板；
- 任务看板第一版**暂不要求拖拽**，先用状态分组列展示；
- 后续如做拖拽，必须先确认状态流转规则和后端接口幂等。

### 5.2 Agent 页

Agent 页面不只是聊天框，至少预留四块区域：

1. 用户输入与模型输出；
2. Agent 工具调用过程（工具名、入参摘要、结果摘要、耗时、状态）；
3. 引用的项目/任务/风险数据；
4. 需要人工确认的动作卡片。

### 5.3 表单与反馈

- 表单使用 Naive UI 校验能力，错误提示为中文；
- 保存、删除、Agent 执行等写操作必须有 loading 和防重复提交；
- 高风险操作必须二次确认，不允许仅靠按钮颜色表达风险。

---

## 六、前端方案输出格式

设计页面或模块时，按以下结构输出：

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

---

## 七、工作流程

1. 先确认页面属于哪个开发阶段，避免提前实现后置能力；
2. 查产品术语表，确保页面文案、组件命名、路由命名统一；
3. 先设计用户路径，再拆组件和状态；
4. 明确 API 依赖，标注后端是否已存在；
5. 优先用 Naive UI 组件解决，必要时用 UnoCSS 做布局微调；
6. 输出验收标准时必须包含手动操作路径。

---

## 八、不可越界

以下事项必须先经用户确认：

- 替换 Vue 3 / Naive UI / Pinia / Axios；
- 同时引入 Tailwind 和 UnoCSS；
- 第一版强行实现任务看板拖拽；
- 引入完整深色模式或移动端适配；
- 绕过统一 Axios 封装直接请求接口；
- 对高风险操作不做确认弹窗；
- 使用未进入术语表的新业务命名。
