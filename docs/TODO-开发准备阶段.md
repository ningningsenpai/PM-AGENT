# 开发准备阶段任务清单（临时文档）

> **用途**：记录第 1 阶段后端编码启动前，所有"准备工作"类任务。等 Skill 全部完善后，按本清单统一调度执行。
> **生命周期**：第 1 阶段后端骨架代码落地后，本文档可归档或删除，正式任务跟踪改走 `docs/01-开发规划.md` + GitHub Issue / TODO。
> **维护原则**：每项任务必须可独立交付；完成后在状态栏打勾，**不删除条目**，便于回溯。

---

## 一、Skill 完善任务

### 1.1 当前 Skill 状态总览

| Skill | 状态 | 优先级 | 阻塞下游 |
|---|---|---|---|
| `pm-agent-backend-architect` | ✅ active | — | — |
| `pm-agent-frontend-builder` | ✅ active | — | — |
| `pm-agent-llm-orchestrator` | ✅ active | — | — |
| `pm-agent-data-modeler` | ✅ active | — | — |
| `pm-agent-product-designer` | ✅ active | — | — |
| `pm-agent-workflow-designer` | ✅ active | — | — |
| `pm-agent-doc-writer` | ✅ active | — | — |
| `pm-agent-test-planner` | ✅ active | — | — |
| `pm-agent-cost-optimizer` | ✅ active | — | — |

### 1.2 完善结果

所有项目级 Skill 已在 2026-06-04 规范为 `active`，并完成以下统一处理：

1. 移除“待用户回答的问题”章节；
2. 将用户已回答的决策落入正文；
3. 明确职责边界：术语表归 `pm-agent-product-designer`，RAG 保持第 6 阶段，统一使用“迭代 / iteration”；
4. 不新增 Skill，现有 9 个项目级 Skill 覆盖当前准备阶段需要。

如后续发生重大方向调整，再单独回到对应 Skill 修订。

---

## 二、文档补齐任务

### 2.1 已有文档

- ✅ `docs/01-开发规划.md`
- ✅ `docs/02-技术选型.md`
- ✅ `docs/03-业务流程.md`
- ✅ `docs/README.md`

### 2.2 已补齐文档

| 文档 | 依赖 Skill | 状态 | 备注 |
|---|---|---|---|
| `docs/00-术语表.md` | `pm-agent-product-designer` | ✅ 已完成 | 统一产品、代码、文档、Agent Prompt 术语 |
| `docs/05-接口规范.md` | `pm-agent-backend-architect` | ✅ 已完成 | 覆盖 v1 前缀、统一响应、traceId、错误码、幂等、权限 |
| `docs/04-数据模型.md` | `pm-agent-data-modeler` | ✅ 已完成 | 覆盖多租户预留、核心表、字典表、Agent Trace |
| `docs/06-Agent设计.md` | `pm-agent-llm-orchestrator` | ✅ 已完成 | 覆盖 Agent 编排、工具调用、Trace、人工确认、RAG 阶段边界 |
| `docs/07-成本控制.md` | `pm-agent-cost-optimizer` | ✅ 已完成 | 覆盖 LLM、Trace、中间件和降级策略 |
| `docs/08-阶段总结.md` | `pm-agent-doc-writer` | ✅ 已完成 | 提供阶段复盘模板与当前准备阶段总结 |

---

## 三、CLAUDE.md / 文档协同修订

本轮已完成跨文档一致性修订：

- ✅ `/api/v1/` 前缀已同步进 `CLAUDE.md`、`docs/01-开发规划.md`、`docs/05-接口规范.md`；
- ✅ 强制 `X-Idempotency-Key` 已写入 `docs/05-接口规范.md`，并在 Skill 与前端/后端设计中对齐；
- ✅ 日志 MDC 字段已写入 `docs/05-接口规范.md`，与 `pm-agent-backend-architect` 一致；
- ✅ Git 管理策略已统一为 Monorepo + `main` 主干 + `feature/*` 任务分支，详见 `docs/12-Git管理策略.md`；
- ✅ 审计日志延期、第 1 阶段仅留注解占位，已与 `docs/01-开发规划.md`、`docs/03-业务流程.md`、`docs/06-Agent设计.md` 对齐；
- ✅ 旧项目名、旧包名、旧迭代表名、旧接口路径、RAG 阶段、模型调用策略等口径已完成扫描和修正。

后续如调整任一核心决策，需要同步更新对应 Skill 与正式文档。

---

## 四、第 1 阶段后端骨架准备任务

> **目的**：Skill 全部 active 后立刻能动手编码，不再临时设计。

### 4.1 工程初始化（已完成开工前决策，待执行）

- ⏳ 创建 `backend/` 目录，初始化 Spring Boot 3 工程（构建工具：**Maven**）；
- ⏳ 包结构按 `com.ning.pm` 落地：`common / config / infrastructure / auth / user / project / task`；
- ⏳ 配置依赖：Sa-Token、MyBatis Plus、Knife4j、Hutool、MapStruct、Lombok、Validation、Flyway、Caffeine；
- ⏳ 配置 `application.yml`：MySQL 连接、Sa-Token 内存模式、`pm.tenant.enabled=false`；
- ⏳ 实现 `common` 模块：
  - 统一响应 `R<T>` + `traceId`
  - `BaseException` / `BizException` / `AgentException` / `SystemException`
  - `ErrorCode` 枚举
  - `GlobalExceptionHandler`
  - `BaseEntity`（含 `tenantId`、`createTime`、`updateTime`、`deleted`）
  - `@AuditLog` 空注解 + AOP 空切面
  - `CurrentUserHolder`
  - Trace 拦截器（写入 MDC）
  - Idempotency 拦截器（第 1 阶段先用 Caffeine）
- ⏳ 配置 Logback `logback-spring.xml`，pattern 包含 traceId/userId/tenantId/action/costMs；
- ⏳ Knife4j 接入与 v1 baseUrl 配置。

### 4.2 数据库初始化

- ⏳ 选定建库方式：**Flyway**；
- ⏳ 第 1 阶段建表清单：`pm_user`、`pm_project`、`pm_project_member`、`pm_task`、`pm_task_status_log`；
- ⏳ 初始化数据：默认用户、示例项目、若干示例任务，用于登录、项目列表和任务看板演示；
- ⏳ 所有表带 `tenant_id BIGINT NOT NULL DEFAULT 0`。

### 4.3 前端骨架准备（与后端并行）

- ⏳ 前端代码统一放在 `frontend/` 目录，当前前端初始化工作按 `feature/init-frontend` 任务分支语义处理；
- ⏳ 使用 Node 20 LTS + pnpm 初始化 `frontend/`，技术栈为 Vite + Vue 3 + TypeScript + Naive UI；
- ⏳ Axios 封装：自动注入 `X-Trace-Id`（前端生成 UUID）、`X-Idempotency-Key`（表单级生成）；
- ⏳ Pinia + Vue Router 基础结构；
- ⏳ 前端提供简单本地 Mock 层，接口未完成前模拟登录、项目、任务数据；
- ⏳ 登录页 + 主布局 + 项目列表页 + 项目详情页 + 任务看板页；
- ⏳ 任务看板第 1 阶段使用下拉框切换任务状态，拖拽能力后置。

### 4.4 Python Agent 服务（第 3 阶段才启动，本阶段仅占位）

- ⏳ 暂不创建 `agent-service/` 目录，等第 3 阶段再启动；
- ⏳ Java 侧 `AgentClient` 接口先以 mock 实现，等 Python 服务上线后切真实地址。

### 4.5 本地开发与 Docker 中间件准备

- ⏳ 创建 `deploy/` 目录；
- ⏳ 使用 Docker 容器承载项目涉及到的中间件；
- ⏳ 第 1 阶段仅启用 MySQL 8 容器；
- ⏳ Redis、RabbitMQ、MinIO、向量库等中间件按阶段在 Docker Compose 中增量加入，默认不提前启动；
- ⏳ 后端 Spring Boot 与前端 Vite 均在本机运行，便于调试；
- ⏳ 后端与前端分别维护环境变量示例文件。

---

## 五、已确认的开工前决策（按主题汇总）

以下决策已完成确认，可作为后续工程初始化依据：

| 编号 | 主题 | 决策结果 | 影响任务 |
|---|---|---|---|
| Q1 | 构建工具 | ✅ 后端使用 Maven | 4.1 工程初始化 |
| Q2 | 数据库迁移 | ✅ 使用 Flyway | 4.2 数据库初始化 |
| Q3 | 节点版本 | ✅ 前端锁定 Node 20 LTS | 4.3 前端骨架 |
| Q4 | 前端包管理 | ✅ 使用 pnpm | 4.3 前端骨架 |
| Q5 | 本地部署 | ✅ Docker 承载中间件，前端和后端本机运行；第 1 阶段仅启用 MySQL | 4.5 Docker 中间件准备 |
| Q6 | 分支策略 | ✅ 单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支；不再使用长期 `frontend` / `backend` 模块分支 | 工程初始化前 |
| Q7 | 第 1 阶段建表范围 | ✅ `pm_user`、`pm_project`、`pm_project_member`、`pm_task`、`pm_task_status_log` | 4.2 数据库初始化 |
| Q8 | `deploy/` 目录 | ✅ 第 1 阶段创建 `deploy/` 目录 | 4.5 Docker 中间件准备 |
| Q9 | 环境变量示例 | ✅ 后端和前端分别维护环境变量示例 | 4.1 / 4.3 |
| Q10 | 初始化数据 | ✅ 初始化默认用户、示例项目、若干示例任务 | 4.2 数据库初始化 |
| Q11 | 前端 Mock | ✅ 使用简单本地 Mock 层模拟接口返回 | 4.3 前端骨架 |
| Q12 | 看板状态切换 | ✅ 第 1 阶段使用下拉框切换任务状态 | 4.3 前端骨架 |

---

## 六、执行调度建议（当前最新）

Skill 与正式文档已全部补齐，后续只剩开工前决策与工程初始化。建议按以下批次推进：

### 批次 A：开工前决策

1. ✅ Q1：后端构建工具使用 Maven；
2. ✅ Q2：数据库迁移方式使用 Flyway；
3. ✅ Q3：前端 Node 版本锁定 Node 20 LTS；
4. ✅ Q4：前端包管理器使用 pnpm；
5. ✅ Q5：Docker 承载中间件，前端和后端本机运行；
6. ✅ Q6：单仓库 Monorepo + `main` 主干 + `feature/*` 任务分支，不再使用长期 `frontend` / `backend` 模块分支；
7. ✅ Q7：第 1 阶段建表范围包含 `pm_project_member` 与 `pm_task_status_log`；
8. ✅ Q8~Q12：`deploy/`、环境变量示例、初始化数据、本地 Mock、看板状态切换方式已确认。

### 批次 B：第 1 阶段工程骨架

1. 将当前前端初始化工作按 `feature/init-frontend` 任务分支语义整理，并合并回 `main`；
2. 从 `main` 创建 `feature/init-backend`，初始化 `backend/` Spring Boot 3 工程；
3. 继续完善 `frontend/` Vue 3 + Vite 工程；
4. 准备 `deploy/` 本地开发配置；
5. 按 `docs/04-数据模型.md` 生成第 1 阶段建表脚本；
6. 按 `docs/05-接口规范.md` 落地统一响应、错误码、traceId、幂等。

### 批次 C：第 1 阶段业务闭环

1. 用户登录与当前用户接口；
2. 项目基础接口与页面；
3. 任务基础接口与看板页面；
4. 手动验收登录、项目、任务、状态流转。

### 批次 D：第 3 阶段前置准备（不阻塞第 1 阶段）

1. 根据 `docs/06-Agent设计.md` 细化 DeepSeek `ModelClient`；
2. 准备 Agent Trace 建表与 Python 服务骨架方案；
3. 真实接入模型后补充 `docs/07-成本控制.md` 成本估算表。

---

## 七、变更记录

| 日期 | 变更 |
|---|---|
| 2026-06-04 | 初版创建，覆盖 Skill / 文档 / 骨架准备 / 决策空白点 / 调度批次 |
