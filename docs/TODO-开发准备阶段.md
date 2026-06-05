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
- ✅ 审计日志延期、第 1 阶段仅留注解占位，已与 `docs/01-开发规划.md`、`docs/03-业务流程.md`、`docs/06-Agent设计.md` 对齐；
- ✅ 旧项目名、旧包名、旧迭代表名、旧接口路径、RAG 阶段、模型调用策略等口径已完成扫描和修正。

后续如调整任一核心决策，需要同步更新对应 Skill 与正式文档。

---

## 四、第 1 阶段后端骨架准备任务

> **目的**：Skill 全部 active 后立刻能动手编码，不再临时设计。

### 4.1 工程初始化（待用户确认后由 Claude 生成）

- ⏳ 创建 `backend/` 目录，初始化 Spring Boot 3 工程（Maven 还是 Gradle？**待确认**）；
- ⏳ 包结构按 `com.ning.pm` 落地：`common / config / infrastructure / project / task / user`；
- ⏳ 配置依赖：Sa-Token、MyBatis Plus、Knife4j、Hutool、MapStruct、Lombok、Validation；
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

- ⏳ 选定建库方式：Flyway / Liquibase / 手写 SQL（**待确认**）；
- ⏳ 第 1 阶段建表清单：`pm_user`、`pm_project`、`pm_task`（依据 `docs/04-数据模型.md`，需先完成）；
- ⏳ 所有表带 `tenant_id BIGINT NOT NULL DEFAULT 0`。

### 4.3 前端骨架准备（与后端并行）

- ⏳ 创建 `frontend/` 目录，Vite + Vue 3 + TS + Naive UI；
- ⏳ Axios 封装：自动注入 `X-Trace-Id`（前端生成 UUID）、`X-Idempotency-Key`（表单级生成）；
- ⏳ Pinia + Vue Router 基础结构；
- ⏳ 登录页 + 任务看板雏形（待 `pm-agent-frontend-builder` 落地后细化）。

### 4.4 Python Agent 服务（第 3 阶段才启动，本阶段仅占位）

- ⏳ 暂不创建 `agent-service/` 目录，等 Skill 与 `docs/06-Agent设计.md` 完成后再启动；
- ⏳ Java 侧 `AgentClient` 接口先以 mock 实现，等 Python 服务上线后切真实地址。

---

## 五、需要用户决策的空白点（按主题汇总）

以下空白点会卡住对应任务，**Skill 完善过程中或开工前需要回答**：

| 编号 | 主题 | 问题 | 卡住的任务 |
|---|---|---|---|
| Q1 | 构建工具 | backend 用 Maven 还是 Gradle？ | 4.1 工程初始化 |
| Q2 | 数据库迁移 | Flyway / Liquibase / 手写 SQL？ | 4.2 数据库初始化 |
| Q3 | 节点版本 | frontend 锁定 Node 版本（18 LTS / 20 LTS）？ | 4.3 前端骨架 |
| Q4 | 测试插件 | 你说"用其他插件"，是 TestMe / Spock / 还是别的？ | `pm-agent-test-planner` Skill |
| Q5 | LLM SDK | 已决策：DeepSeek 优先 + 自研轻量 `ModelClient` 适配层 | 第 3 阶段前细化 |
| Q6 | 部署 | 本地 docker-compose 全栈起？还是仅 MySQL 用 Docker、应用本机跑？ | `deploy/` 目录、第 1 阶段联调 |
| Q7 | 仓库 | 是否需要初始化 Git 仓库 + .gitignore + 提交规范钩子？ | 工程初始化前 |

---

## 六、执行调度建议（当前最新）

Skill 与正式文档已全部补齐，后续只剩开工前决策与工程初始化。建议按以下批次推进：

### 批次 A：开工前决策

1. 回答 Q1：后端构建工具（Maven / Gradle）；
2. 回答 Q2：数据库迁移方式（Flyway / Liquibase / 手写 SQL）；
3. 回答 Q3：前端 Node 版本；
4. 回答 Q6：本地部署方式；
5. 回答 Q7：是否初始化 Git 仓库。

### 批次 B：第 1 阶段工程骨架

1. 初始化 `backend/` Spring Boot 3 工程；
2. 初始化 `frontend/` Vue 3 + Vite 工程；
3. 准备 `deploy/` 本地开发配置；
4. 按 `docs/04-数据模型.md` 生成第 1 阶段建表脚本；
5. 按 `docs/05-接口规范.md` 落地统一响应、错误码、traceId、幂等。

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
