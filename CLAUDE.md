# CLAUDE.md

本文件用于指导 Claude Code 在本仓库（PM-AGENT）中协助开发，覆盖项目背景、技术选型、开发规范、AI 协作策略与开发节奏。所有 Claude Code 会话在开始前都应阅读本文件。

---

## 一、项目概述

### 1.1 项目名称

**PM-Agent 智能项目管理 Agent 平台**

### 1.2 项目定位

基于 Java + Python + 大模型 Agent 构建的智能项目管理平台，面向项目经理、研发团队与管理层，支持：

- 项目、需求、任务、迭代、风险、报告等结构化业务管理；
- 通过 Agent 自动分析项目状态、识别风险、生成周报、拆解需求；
- 通过 RAG 沉淀和检索项目知识、会议纪要与历史经验。

### 1.3 项目目标

> 帮助项目经理和研发团队自动理解项目状态、发现风险、生成报告、推动任务执行，从而提升项目交付效率。

### 1.4 项目规模

- 开发模式：**单人 + AI 协作**；
- 月度 LLM 预算：**200 至 600 元人民币**；
- 优先级：开发速度与效果 > 成本；可接受较高开发成本，但运行时成本须严格控制。

---

## 二、技术栈

### 2.1 前端

| 类别 | 选型 |
|---|---|
| 框架 | Vue 3 |
| 语言 | TypeScript |
| 构建 | Vite |
| 组件库 | Naive UI |
| 状态管理 | Pinia |
| 路由 | Vue Router |
| 图表 | ECharts |
| HTTP 客户端 | Axios |
| 样式增强 | UnoCSS 可选 |

选择理由：Naive UI 视觉更现代、轻量、不冗余，TypeScript 支持友好，适合单人开发与可读性优先的后台管理系统。

### 2.2 Java 后端

| 类别 | 选型 |
|---|---|
| 框架 | Spring Boot 3 |
| ORM | MyBatis Plus |
| 认证授权 | Sa-Token |
| API 文档 | Knife4j / OpenAPI |
| 校验 | Jakarta Validation |
| 工具 | Hutool / MapStruct |

选择理由：Sa-Token 上手快、代码轻量、权限直观，适合单人项目和后台管理系统；相比 Spring Security，可显著减少配置负担。

### 2.3 Python Agent 服务

| 类别 | 选型 |
|---|---|
| 框架 | FastAPI |
| 数据校验 | Pydantic |
| 异步任务 | Celery（后期引入） |
| Agent 编排 | 自研轻量编排为主，必要时引入 LangChain / LlamaIndex |
| 向量检索 | Qdrant 或 pgvector（RAG 阶段引入） |

选择理由：Python 用于 Agent 推理、Prompt 编排、RAG 检索，避免污染 Java 业务主链路。

### 2.4 数据库与中间件

| 中间件 | 引入阶段 | 用途 |
|---|---|---|
| MySQL 8 | 第 1 阶段 | 业务数据存储 |
| Redis 7 | 第 2 阶段 | 缓存、Sa-Token 会话、限流 |
| RabbitMQ | 第 5 阶段 | 异步任务、通知、风险扫描 |
| MinIO | 第 6 阶段 | 文档、附件、报告文件 |
| Qdrant 或 pgvector | 第 6 阶段 | 向量检索 |
| Elasticsearch | 可选后置 | 全文检索 |
| Prometheus + Grafana | 后期 | 系统监控 |

原则：**按阶段引入，不一次性堆所有中间件。**

---

## 三、目录结构（规划）

```text
PM-AGENT/
├── CLAUDE.md                       # 本文件
├── .claude/                        # Claude Code 项目级配置
│   └── skills/                     # 正式英文项目级 Skill（开发调用优先使用）
│       ├── pm-agent-product-designer/
│       ├── pm-agent-backend-architect/
│       ├── pm-agent-frontend-builder/
│       ├── pm-agent-data-modeler/
│       ├── pm-agent-workflow-designer/
│       ├── pm-agent-llm-orchestrator/
│       ├── pm-agent-test-planner/
│       ├── pm-agent-doc-writer/
│       └── pm-agent-cost-optimizer/
├── BaseSkill-CN/                   # 中文参考 Skill，非开发调用，仅供对照审阅
│   ├── README.md
│   ├── _base-template/
│   ├── pm-agent-product-designer/
│   ├── pm-agent-backend-architect/
│   ├── pm-agent-frontend-builder/
│   ├── pm-agent-data-modeler/
│   ├── pm-agent-workflow-designer/
│   ├── pm-agent-llm-orchestrator/
│   ├── pm-agent-test-planner/
│   ├── pm-agent-doc-writer/
│   └── pm-agent-cost-optimizer/
├── docs/                           # 项目文档
│   ├── 00-术语表.md
│   ├── 01-开发规划.md
│   ├── 02-技术选型.md
│   ├── 03-业务流程.md
│   ├── 04-数据模型.md
│   ├── 05-接口规范.md
│   ├── 06-Agent设计.md
│   ├── 07-成本控制.md
│   └── 08-阶段总结.md
├── backend/                        # Java Spring Boot 后端（待创建）
├── agent-service/                  # Python FastAPI Agent 服务（待创建）
├── frontend/                       # Vue 3 前端（待创建）
└── deploy/                         # 部署脚本与 docker-compose（待创建）
```

---

## 四、开发规范

### 4.1 语言规范

- 所有对话和文档：**统一使用中文**；
- 代码注释：**统一使用中文**；
- 错误提示：**统一使用中文**；
- 文档格式：**统一使用 Markdown**；
- `.claude/skills/` 下的正式 Skill 文档允许使用英文，以便符合 Claude Code Skill 调用规范；
- `BaseSkill-CN/` 下的中文 Skill 仅供对照审阅，不作为正式开发调用来源。

### 4.2 命名规范

- Java 包名：`com.ning.pm.<module>`；
- Java 类名：大驼峰；
- Java 方法和变量：小驼峰；
- 数据库表名：小写下划线，业务前缀，例如 `pm_project`、`pm_task`、`agent_trace`；
- 前端组件：大驼峰；
- 前端文件名：短横线 kebab-case；
- 接口路径：`/api/v1/<module>/<resource>`；

### 4.3 注释规范

- 关键类与方法必须有中文注释，说明用途、入参、出参；
- 复杂业务逻辑必须解释“为什么这么做”，而不仅仅是“做了什么”；
- 临时代码必须用 `// TODO 中文说明` 标注，禁止留下未说明的注释。

### 4.4 接口与错误码

- 响应结构：

  ```json
  {
    "code": 0,
    "message": "成功",
    "data": {},
    "traceId": "abc123def456"
  }
  ```

- 错误码分段：

  ```text
  0           成功
  1xxxx       通用错误
  2xxxx       用户与权限
  3xxxx       项目与任务
  4xxxx       Agent 与 LLM
  5xxxx       外部服务
  9xxxx       系统错误
  ```

### 4.5 提交规范（建议）

采用 Conventional Commits：

```text
feat: 新功能
fix: 修复
docs: 文档
refactor: 重构
chore: 杂项
test: 测试
perf: 性能优化
```

---

## 五、开发阶段规划

> 原则：**前后端垂直切片，按模块闭环；技术点解耦，新增中间件按阶段引入。**

| 阶段 | 核心目标 | 后端 | 前端 | 新增技术点 |
|---|---|---|---|---|
| 第 1 阶段 | 项目基础骨架 | Spring Boot + Sa-Token + MySQL；用户、项目、任务基础接口 | Vue3 + Naive UI 骨架、登录页、项目列表、任务看板 | Spring Boot 3、Sa-Token、MyBatis Plus、Naive UI |
| 第 2 阶段 | 项目管理 MVP | 需求、迭代、任务依赖、风险表 | 项目详情、需求管理、风险列表、看板拖拽 | Redis、RBAC、状态机 |
| 第 3 阶段 | Agent 对话能力 | Java 透传层 + Python FastAPI；Agent 对话接口、Trace 存储 | Agent 助手页、项目问答入口、流式输出 | FastAPI、Prompt 模板、模型路由 |
| 第 4 阶段 | Agent 工具调用 | 工具 API（查询项目、任务、生成周报、拆分需求） | 一键周报、需求拆任务交互 | Tool Calling、Agent Trace 可视化 |
| 第 5 阶段 | 风险分析与异步任务 | 延期识别、阻塞分析、人员负载、风险评分 | 风险中心、风险详情、Agent 建议卡片 | RabbitMQ、定时任务、规则引擎 |
| 第 6 阶段 | RAG 知识库 | 文档上传、解析、切片、向量化 | 文档管理、会议纪要、知识问答 | MinIO、Qdrant/pgvector、RAG 链路 |
| 第 7 阶段 | 企业级完善 | 通知、审计、报告导出、多项目统计 | 数据看板、报表中心、系统设置 | ECharts 看板、通知渠道、监控 |

**MVP 范围（第 1–2 阶段）**：用户登录、项目管理、任务管理、任务看板、风险手动登记。

---

## 六、Agent 设计原则

详细方案见 `docs/06-Agent设计.md`。核心约束如下：

1. Agent 不直接操作数据库，所有业务变更必须通过工具 API；
2. 高风险操作（删除、修改权限、对外通知）必须人工确认；
3. 所有 Agent 决策必须落库到 `agent_trace`，包含输入、Prompt、工具调用、模型输出、最终结论；
4. 模型输出应尽量结构化，关键字段使用 JSON Schema 或 Pydantic 校验；
5. Agent 必须能识别信息不足并追问，禁止凭空补全关键业务字段。

---

## 七、LLM 模型策略

### 7.1 运行时模型分层

| 业务能力 | 默认模型 | 升级模型 |
|---|---|---|
| 意图识别 | DeepSeek | Claude |
| 需求拆解 | DeepSeek 起草 | Claude / GPT |
| 周报生成 | DeepSeek 起草 | Claude 润色 |
| 风险分析 | DeepSeek / 规则结果 | Claude / GPT |
| 会议纪要提取 | DeepSeek | Gemini / Claude |
| RAG 问答 | DeepSeek | Claude |
| 项目问答 | DeepSeek | Claude |

### 7.2 开发期模型分工

| 开发任务 | 首选 | 备选 |
|---|---|---|
| 系统架构设计 | Claude | GPT |
| 后端代码开发 | Claude | DeepSeek |
| 前端代码开发 | Claude | GPT |
| 前端界面设计 | Claude + frontend-design skill | GPT |
| 数据库设计 | Claude + database-schema-designer skill | GPT |
| API 文档撰写 | GPT / Claude | DeepSeek |
| 技术文档撰写 | Claude | GPT |
| 产品设计 | GPT / Claude | DeepSeek |
| 业务流程设计 | Claude | GPT |
| 代码规范审查 | Claude + code-review skill | DeepSeek |

### 7.3 成本控制原则

- 项目运行时默认使用低成本模型（DeepSeek 优先）；
- 关键决策、长文档生成、最终润色使用 Claude；
- 文档切片、摘要等批量任务必须缓存结果；
- Agent Trace 开发与调优阶段保留必要 Prompt、模型输出和工具调用结果；运行期按 3 个月保留策略控制存储成本。

---

## 八、Claude Code 使用规范

### 8.1 必须遵守

1. 所有对话和文档使用中文；
2. 所有代码注释使用中文；
3. 修改文件前先 Read，不要凭印象编辑；
4. 涉及多模块改动时，先列出计划，再执行；
5. 不主动引入 CLAUDE.md 中未列出的中间件或框架，必须先经用户确认；
6. 不主动改动已确定的技术选型（Sa-Token、Naive UI 等）。

### 8.2 建议遵守

1. 优先使用项目内正式 Skill（位于 `.claude/skills/`）；`BaseSkill-CN/` 仅用于和正式 Skill 对照审阅；
2. 设计阶段优先输出 Markdown 文档到 `docs/`，再进入代码实现；
3. 单次任务尽量限定在一个阶段、一个模块，避免跨阶段堆叠；
4. 涉及 Agent 设计的改动必须更新 `docs/06-Agent设计.md`。

### 8.3 输出格式

Claude 在生成代码、设计或文档时默认输出结构：

```markdown
## 背景
## 方案
## 改动点
## 验收标准
## 风险与待确认
```

---

## 九、项目级 Skill

详见 `.claude/skills/`。所有项目级正式 Skill 均为英文 `active` 状态，后续设计与实现优先遵守对应正式 Skill。`BaseSkill-CN/` 仅作为中文参考副本，用于和正式 Skill 对照审阅。

| Skill | 用途 | 优先级 |
|---|---|---|
| pm-agent-product-designer | 产品边界、角色、模块、术语 | 高 |
| pm-agent-backend-architect | Java 分层、接口、权限、异常 | 高 |
| pm-agent-frontend-builder | Vue 页面、组件、路由、状态 | 高 |
| pm-agent-data-modeler | 数据模型与演进 | 高 |
| pm-agent-workflow-designer | 状态机、流程、审批、通知 | 中高 |
| pm-agent-llm-orchestrator | Agent、工具调用、Prompt、Trace | 高 |
| pm-agent-test-planner | 测试策略与用例 | 中 |
| pm-agent-doc-writer | 项目文档统一风格 | 中 |
| pm-agent-cost-optimizer | LLM 与中间件成本控制 | 中 |

**最优先完善的三个**：`pm-agent-backend-architect`、`pm-agent-frontend-builder`、`pm-agent-llm-orchestrator`。

---

## 十、相关文档

| 文档 | 位置 | 用途 |
|---|---|---|
| 开发规划 | `docs/01-开发规划.md` | 分阶段任务清单 |
| 技术选型 | `docs/02-技术选型.md` | 详细技术选型说明 |
| 业务流程 | `docs/03-业务流程.md` | 项目、任务、风险、报告等流程 |
| 数据模型 | `docs/04-数据模型.md` | 表结构与关系 |
| 接口规范 | `docs/05-接口规范.md` | API 命名、错误码、响应结构 |
| Agent 设计 | `docs/06-Agent设计.md` | Agent 编排、工具、Trace |
| 成本控制 | `docs/07-成本控制.md` | LLM 与中间件成本方案 |
| 阶段总结 | `docs/08-阶段总结.md` | 每个阶段复盘 |

---

## 十一、当前状态

- 已完成：项目定位、技术选型、9 个项目级 Skill 规范化、`docs/00~08` 文档体系搭建；
- 进行中：第 1 阶段编码前的工程初始化决策确认；
- 下一步：确认构建工具、数据库迁移方式、Node 版本、Git 初始化与本地部署方式，然后启动第 1 阶段后端与前端骨架开发。
