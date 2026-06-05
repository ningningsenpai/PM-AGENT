---
name: pm-agent-product-designer
description: Product design skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user discusses product positioning, user roles, business boundaries, MVP scope, product modules, page capabilities, interaction flows, acceptance criteria, requirement priorities, or the shared product glossary. It turns rough ideas into buildable, traceable product plans for PM-Agent.
metadata:
  status: active
  language: en-US
  owner_module: product
  related_docs:
    - docs/00-术语表.md
    - docs/01-开发规划.md
    - docs/03-业务流程.md
---

# PM-Agent Product Design Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing project modules, pages, feature lists, or MVP scope;
- Clarifying perspectives for project managers, developers, testers, leadership, or solo developers;
- Turning verbal ideas into product requirements, user stories, and acceptance criteria;
- Deciding whether a feature belongs in the current phase or should be deferred;
- Defining or maintaining the shared product glossary;
- Reviewing business boundaries to avoid mixing project management, knowledge base, BI, OA, and DevOps capabilities into the first version.

## Goal

Help Claude design PM-Agent as an intelligent project management Agent platform by clarifying users, boundaries, feature priorities, business flows, terminology, and acceptance criteria. The goal is to ensure backend, frontend, data modeling, and Agent design all use the same product language.

---

## 1. Product positioning and priorities

### 1.1 Primary first-version user

The first version targets **solo developers / single-person project managers** first. Prioritize project, requirement, task, risk, and Agent-assisted analysis needs for individuals or small teams.

### 1.2 First-version value focus

The first version should emphasize **Agent-powered analysis**, but it must not become only a demo chat page. The basic business logic for projects, tasks, risks, and related entities must be confirmed so the Agent has real business data to analyze.

### 1.3 MVP scope principles

1. The MVP should cover the core business loop as completely as possible; weaker UX or automation is acceptable where necessary.
2. Prioritize business logic, entity relationships, state transitions, and Agent intervention points.
3. Design the first version around personal project management. Enterprise-grade multi-tenancy, complex RBAC, and full approval workflows are deferred.
4. Each phase must produce a closed-loop frontend + backend demonstration. Avoid building only backend or only pages.

---

## 2. Module boundaries

### 2.1 Core modules

| Module | First-version positioning | Out of scope |
|---|---|---|
| Project management | Basic project info, members, progress overview | No complex project portfolio management |
| Requirement management | Requirement records, priority, decomposition entry point | No full requirement review workflow |
| Task management | Task creation, assignment, state transition, kanban display | No complex drag-and-drop dependency orchestration in v1 |
| Iteration management | A unified time-cycle container for Agile Sprint and waterfall phases | No full methodology configuration platform |
| Risk management | Risk registration, Agent detection, PM confirmation, handling follow-up | No enterprise-grade risk approval process |
| Agent assistant | Project Q&A, risk analysis, requirement decomposition, weekly report draft | Must not bypass business APIs to modify the database |
| Report center | Weekly report draft generation and human editing/confirmation | No complex reporting platform in v1 |

### 2.2 Phase control

- Phases 1-2: core business loop for projects, requirements, tasks, iterations, and risks;
- Phases 3-4: Agent chat, tool calling, Trace, requirement decomposition, weekly report drafts;
- Phase 5: risk analysis, asynchronous tasks, rule-based enhancements;
- Phase 6: RAG knowledge base; do not pull it into the first version early;
- Phase 7: notifications, audit, report export, dashboards, enterprise enhancements.

---

## 3. Shared product glossary

This skill owns `docs/00-术语表.md`. Other skills should reference and follow the glossary instead of inventing new terms independently.

### 3.1 Terminology governance rules

1. Before adding a business concept, check whether an existing term can be reused.
2. If a new term is truly needed, update `docs/00-术语表.md` before data modeling, API design, or frontend page design.
3. The glossary must include: standard Chinese name, English identifier, one-sentence definition, scope boundary, disallowed synonyms, and related terms.
4. Code names, table names, API paths, page copy, and Prompt templates must use the standard terms in the glossary.
5. The Agent may recognize synonyms, but user-facing output must return to standard terms.

### 3.2 Confirmed core terms

| Standard term | English identifier | Description |
|---|---|---|
| 项目 | project | An independent delivery goal containing requirements, tasks, risks, reports, and related data |
| 需求 | requirement | A user-facing business need that can be decomposed into tasks |
| 任务 | task | The smallest development execution unit managed by the system |
| 迭代 | iteration | A unified time cycle covering both Agile Sprint and waterfall phases; use `iteration` in code, table names, and APIs. Sprint/phase are synonyms only |
| 风险 | risk | An uncertain factor that may affect delivery, distinct from an already-occurring issue |
| 问题 | issue | A matter that has already occurred and affects progress or quality |
| 报告 | report | Structured outputs such as weekly reports and phase reports |
| Agent | agent | An intelligent executor with tool-calling and reasoning ability, not the underlying model itself |
| 工具 | tool | A controlled business capability API callable by the Agent |
| Trace | trace | A traceable record of one Agent decision |

---

## 4. Product plan output format

When designing a module or feature, use this structure:

```markdown
# 产品方案：[模块/功能名称]

## 背景
（为什么现在要做，属于哪个阶段）

## 目标用户
（第一版优先个人开发者 / 单人项目管理者；如面向其他角色需说明）

## 业务价值
（解决什么问题，为什么值得做）

## 涉及术语
（复用术语 / 新增术语 / 禁用同义词；如新增术语，提示更新 docs/00-术语表.md）

## 功能范围
### 必须做
### 建议做
### 后置做

## 页面与交互
（页面清单、关键操作路径、状态反馈）

## 核心流程
（用步骤或 Mermaid 表达）

## 字段与规则
（关键字段、校验、状态、权限、Agent 介入点）

## MVP 范围
（当前阶段具体落地内容）

## 后续增强
（明确后续阶段，不混入当前实现）

## 验收标准
（可手动验收、可演示）

## 待确认问题
（只列真正影响设计或实现的问题）
```

Keep the section headings and user-facing document content in Chinese to comply with project language rules.

---

## 5. Workflow

1. Align with the current phase and decide whether the feature is MVP, later enhancement, or out of scope.
2. Check `docs/00-术语表.md` for related terms.
3. Clarify target users and business value; do not derive product requirements only from technical plans.
4. Split scope into must-have / recommended / deferred to control delivery size.
5. Produce a product plan that backend, frontend, data modeling, and Agent skills can refine further.
6. For high-risk operations, Agent-written business changes, or permission changes, define the human-confirmation boundary.

---

## 6. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Adding a core business concept without entering it into the glossary;
- Pulling Phase 6 RAG or Phase 7 enterprise capabilities into the first version;
- Adding full approval workflows, complex OA, BI, DevOps, or organization-level SaaS capability in v1;
- Changing confirmed terminology, such as replacing `iteration` with `sprint` or `phase` as the primary term;
- Letting the Agent automatically execute deletion, permission changes, external notifications, or other high-risk actions without human confirmation.
