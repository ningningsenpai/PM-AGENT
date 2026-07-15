# PM-Agent · 智能项目管理 Agent 平台

> 把项目状态变成可追踪的执行线索。

PM-Agent 是一个面向项目经理与研发团队的智能项目管理平台，采用 **Vue 3 + Spring Boot 3 + Python Agent** 的渐进式架构：先完成传统项目管理 MVP（项目、需求、任务、迭代、风险、报告），再逐步接入 Agent 对话、工具调用、风险分析、周报生成与 RAG 知识库能力。

项目按 **单人 + AI 协作** 的节奏推进，强调阶段交付、技术解耦与运行时成本可控。

---

## ✨ 项目目标

- 让项目、需求、任务、迭代、风险、报告等数据**结构化沉淀**；
- 让 Agent 在真实业务数据之上**自动分析项目状态、识别风险、生成报告、拆解需求**；
- 让每一次 Agent 决策都可以**通过 Trace 追溯**；
- 保持**单人开发可维护**、**运行成本可控**、**阶段可演示**。

---

## 🚦 当前状态

PM-Agent 当前的 Java 后端处于 **认证与项目文件基座阶段**，支持无租户隔离的多用户邮箱登录、最小项目归属和MinIO文件管理；完整项目管理与Agent业务能力仍未恢复。

| 模块 | 状态 | 说明 |
|---|---|---|
| 文档体系 | ✅ 已完成基础版 | 术语、规划、技术选型、业务流程、数据模型、接口规范、Agent 设计、Git 管理、Figma 设计 |
| 前端工程 | ✅ 已初始化 | Vue 3 + TS + Vite + Naive UI，包含项目介绍、登录、注册、项目列表、任务看板与 Mock 层 |
| 后端工程 | ✅ 认证与文件基座已完成 | Spring Boot 3 + Sa-Token JWT + MyBatis Plus + Flyway + MinIO，含统一响应、日志和 traceId |
| 用户认证 | ✅ 已完成 | 用户注册、邮箱登录、登出、当前用户资料和密码修改 |
| 本地中间件 | ✅ MySQL、MinIO已启用 | Docker Compose启动MySQL 8和MinIO |
| 项目文件接口 | ✅ 最小能力已完成 | 用户—项目—business—文件层级、双哈希、同对象键覆盖和临时只读地址 |
| 完整项目 / 任务接口 | ⏸️ 未恢复 | 当前只提供文件归属所需的最小项目创建与查询 |
| Figma 业务界面 | ✅ 已完成第一版 | 项目总览、项目管理、任务看板、风险中心、PM 助手、报告中心、系统设置、用户中心 |
| Python Agent 服务 | 🗓️ 规划中 | 第 3 阶段引入 |
| Agent 工具调用 | 🗓️ 规划中 | 第 4 阶段引入 |
| 自动风险分析 | 🗓️ 规划中 | 第 5 阶段引入 |
| RAG 知识库 | 🗓️ 规划中 | 第 6 阶段引入 |
| 通知 / 审计 / 报表 / 看板 | 🗓️ 规划中 | 第 7 阶段引入 |

---

## 🧩 核心能力

### 已具备基础

- Vue 3 + TypeScript + Naive UI 前端骨架，包含公开介绍页与认证页；
- Spring Boot 3 + Sa-Token JWT 后端骨架；
- MyBatis Plus + Flyway 数据迁移；
- 统一响应结构和 traceId 链路追踪；
- 用户注册、登录、登出、当前用户接口；
- 项目文件空间、MinIO上传与同对象键覆盖；
- 本地Docker MySQL和MinIO中间件配置。

### 规划能力

- 项目 / 需求 / 任务 / 迭代 / 风险 / 报告业务闭环；
- 基于项目数据的 Agent 项目问答；
- 工具调用：项目查询、任务查询、需求拆解、周报草稿、风险候选；
- 自动风险分析与处理建议；
- RAG 知识库与项目文档问答；
- 通知中心、审计日志、报表、数据看板。

---

## 🏗️ 架构概览

```text
Vue 3 + TypeScript（Naive UI / Pinia / Vue Router）
        │ HTTP/JSON
        ▼
Java Spring Boot 3（Sa-Token / MyBatis Plus / Flyway）
        │ HTTP + SSE + 工具 API
        ▼
Python FastAPI Agent 服务（第 3 阶段引入）
        │
        ▼
LLM API（DeepSeek 优先） / 向量库（第 6 阶段）
```

---

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、Naive UI、Pinia、Vue Router、Axios、ECharts |
| 后端 | Java 17、Spring Boot 3、Maven、Sa-Token、MyBatis Plus、Flyway、MinIO Java SDK、Knife4j、Jakarta Validation |
| Agent 服务 | Python FastAPI、Pydantic v2（**规划中，第 3 阶段引入**） |
| 数据库 | MySQL 8（**当前已启用**） |
| 中间件 | MySQL、MinIO当前启用；Redis、RabbitMQ、Qdrant或pgvector按后续阶段引入 |
| LLM | DeepSeek 优先；Claude / GPT 用于复杂推理、关键判断和最终润色 |
| 部署 | Docker Compose 管理本地中间件，前后端本机运行 |

模型与中间件均按阶段引入，不一次性堆叠。月度运行时 LLM 成本目标约 600 元人民币以内。

---

## 📁 仓库结构

```text
PM-AGENT/
├── frontend/        # Vue 3 前端工程
├── backend/         # Spring Boot 后端工程
├── agent-service/   # 独立 Python Agent 服务
├── deploy/          # 本地中间件与部署配置
├── docs/            # 项目长期文档
├── .claude/         # Claude Code 项目级配置与 Skill
└── CLAUDE.md        # 项目协作规范
```

`agent-service/`与当前Java认证及文件基座独立演进，Java后端暂不调用该服务；文件路径与哈希规则保持可对接。

仓库采用 **单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支**，详见 [docs/12-Git管理策略.md](./docs/12-Git管理策略.md)。

---

## 🚀 本地快速启动

环境要求：

- JDK 17+
- Maven 3.9+
- Node.js 20 LTS
- pnpm 9+
- Docker / Docker Compose

### 1. 启动本地 MySQL

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

详见 [deploy/README.md](./deploy/README.md)。

### 2. 启动后端

```bash
cd backend
mvn spring-boot:run
```

健康检查：`GET http://localhost:8080/internal/health`  
接口文档：`http://localhost:8080/doc.html`

### 3. 启动前端

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

前端默认运行在 `http://localhost:5173`，通过 Vite 代理调用后端 `http://localhost:8080`。

启动后访问 `/` 查看项目介绍页，`/login` 与 `/register` 完成认证后进入工作台。

---

## 🎬 当前可演示内容

| 能力 | 状态 | 演示入口 |
|---|---|---|
| 后端健康检查 | ✅ 已完成 | `GET http://localhost:8080/internal/health` |
| API 调试文档 | ✅ 已完成 | `http://localhost:8080/doc.html` |
| 用户注册 | ✅ 已完成 | `POST /api/v1/auth/register` |
| 用户登录 | ✅ 已完成 | `POST /api/v1/auth/login` |
| 用户登出 | ✅ 已完成 | `POST /api/v1/auth/logout` |
| 当前用户 | ✅ 已完成 | `GET /api/v1/users/me` |
| 前端介绍页 | ✅ 已完成 | `http://localhost:5173/` |
| 前端登录 / 注册页 | 🚧 联调中 | `http://localhost:5173/login`、`/register` |
| 项目 / 任务业务闭环 | 🚧 进行中 | 第 1 阶段接口补齐后演示 |
| Agent 对话与 RAG | 🗓️ 规划中 | 第 3 阶段后逐步引入 |

---

## 🗺️ Roadmap

| 阶段 | 主题 | 状态 |
|---|---|---|
| 第 1 阶段 | 项目骨架：用户、项目、任务最小闭环 | 进行中 |
| 第 2 阶段 | 项目管理 MVP：需求、迭代、风险、看板、RBAC | 规划中 |
| 第 3 阶段 | Agent 对话：项目问答、流式输出、会话历史 | 规划中 |
| 第 4 阶段 | Agent 工具调用：需求拆解、周报草稿、状态查询 | 规划中 |
| 第 5 阶段 | 风险分析：延期识别、阻塞分析、异步任务 | 规划中 |
| 第 6 阶段 | RAG 知识库：文档管理、知识问答、引用来源 | 规划中 |
| 第 7 阶段 | 企业级完善：通知、审计、报表、数据看板 | 规划中 |

详细阶段交付物见 [docs/01-开发规划.md](./docs/01-开发规划.md)。

---

## 📚 文档导航

- [docs/README.md](./docs/README.md)：文档总索引
- [docs/01-开发规划.md](./docs/01-开发规划.md)：阶段路线图
- [docs/02-技术选型.md](./docs/02-技术选型.md)：技术栈与中间件阶段策略
- [docs/03-业务流程.md](./docs/03-业务流程.md)：业务对象与状态流转
- [docs/04-数据模型.md](./docs/04-数据模型.md)：表结构与 Agent Trace
- [docs/05-接口规范.md](./docs/05-接口规范.md)：API、错误码、traceId
- [docs/06-Agent设计.md](./docs/06-Agent设计.md)：Agent、工具、Trace、成本边界
- [docs/10-第1阶段业务流程与验收清单.md](./docs/10-第1阶段业务流程与验收清单.md)：第 1 阶段闭环与验收
- [docs/12-Git管理策略.md](./docs/12-Git管理策略.md)：Monorepo 与分支策略
- [docs/13-用户认证模块设计.md](./docs/13-用户认证模块设计.md)：认证模块设计
- [docs/Figma界面设计文档.md](./docs/Figma界面设计文档.md)：Figma 页面设计依据
- [CLAUDE.md](./CLAUDE.md)：项目协作规范与 Claude Code 使用约定
- [deploy/README.md](./deploy/README.md)：本地中间件操作手册

---

## 🤝 协作与贡献

PM-Agent 当前以单人 + AI 协作开发为主，欢迎通过 Issue 反馈想法、问题与建议。所有提交遵循 Conventional Commits，例如：

```text
feat(auth): 实现用户注册登录基础接口
docs(figma): 更新第一阶段界面设计文档
```

---

## 📄 License

License：待定。当前阶段暂不主动选择 MIT、Apache-2.0 等开源协议，后续根据项目发布方式再确认。
