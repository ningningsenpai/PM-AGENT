---
name: pm-agent-data-modeler
description: Data modeling skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user designs database tables, fields, indexes, relationships, data dictionaries, state enums, logical deletion, multi-tenant fields, audit tables, Agent Trace tables, or decides how business data should be stored in MySQL, vector databases, or search engines.
metadata:
  status: active
  language: en-US
  owner_module: data
  related_docs:
    - docs/00-术语表.md
    - docs/04-数据模型.md
    - docs/06-Agent设计.md
---

# PM-Agent Data Modeling Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing business tables for projects, requirements, tasks, iterations, risks, reports, and related domains;
- Designing fields, indexes, unique constraints, foreign-key strategy, or logical deletion strategy;
- Designing state enums, data dictionaries, and state-transition logs;
- Designing Agent Trace, tool-call logs, or LLM message records;
- Deciding what belongs in MySQL, vector storage, file storage, or search engines;
- Reviewing whether a data model supports current-phase queries, statistics, and future extension.

## Goal

Help Codex design a stable, extensible, low-rework data model for PM-Agent. The model should make business relationships clear, query paths explicit, and Agent traces reproducible, while avoiding over-generalization in the first version.

---

## 1. Technical baseline

| Item | Choice / rule |
|---|---|
| Primary database | MySQL 8 |
| ORM | MyBatis Plus |
| Deletion strategy | Logical deletion by default; some large tables may later be archived by date or physically cleaned |
| ID strategy | Use auto-increment for performance-first tables; use Snowflake IDs for sensitive or distribution-sensitive tables; do not use UUID except for traceId |
| State enums | Store string codes in the database, not numbers |
| Multi-tenancy | Reserve `tenant_id BIGINT NOT NULL DEFAULT 0` on all business tables |
| Agent Trace retention | 3 months, no archive for now |
| Data dictionary | Required for unified management |

---

## 2. Core modeling principles

1. Model around real business relationships first; do not abstract early for a “generic platform”.
2. Table names, field names, and enum codes must follow `docs/00-术语表.md`.
3. State fields must have corresponding state-transition logs for review and Agent analysis.
4. Agent-related logs are modeled independently and must not be mixed into business tables.
5. Design indexes around query scenarios; do not mechanically index every field.
6. The first version prioritizes a closed business loop. RAG document/vector models belong to Phase 6 and must not be implemented early as a full chain.

---

## 3. Common field conventions

### 3.1 BaseEntity fields

All business tables include these fields by default:

| Field | Type | Description |
|---|---|---|
| `id` | BIGINT | Primary key; auto-increment or Snowflake depending on table strategy |
| `tenant_id` | BIGINT NOT NULL DEFAULT 0 | Multi-tenant reservation; fixed to 0 in Phase 1 |
| `created_by` | BIGINT NULL | Creator |
| `created_at` | DATETIME NOT NULL | Creation time |
| `updated_by` | BIGINT NULL | Updater |
| `updated_at` | DATETIME NOT NULL | Update time |
| `deleted` | TINYINT NOT NULL DEFAULT 0 | Logical deletion flag |

### 3.2 Naming conventions

| Object | Rule | Example |
|---|---|---|
| Business table | `pm_` prefix + glossary English identifier | `pm_project`, `pm_task`, `pm_iteration` |
| Agent table | `agent_` prefix | `agent_trace`, `agent_tool_call` |
| System table | `sys_` prefix | `sys_dict_type`, `sys_dict_item` |
| Field | lowercase snake_case | `project_id`, `risk_level` |
| State field | `status` or `{domain}_status` | `status`, `approval_status` |

---

## 4. ID strategy

| Scenario | Strategy | Description |
|---|---|---|
| Ordinary business main tables | Auto-increment BIGINT | Simple and performant for a single-node MVP |
| Sensitive tables or tables where scale should not be exposed | Snowflake ID | Example: Agent Trace or externally visible report numbers |
| traceId | UUID string without hyphens | Only for chain tracing, not a business primary key |
| Frontend temporary key | UUID | Example: `X-Idempotency-Key`; not a business primary key |

---

## 5. State enums and data dictionary

### 5.1 State enums

1. Store string codes in the database, such as `pending`, `in_progress`, and `done`.
2. States that affect business branches must also be constrained by Java / Python enums.
3. Dictionary tables provide display names, colors, and ordering; they do not decide whether a business state transition is legal.
4. Do not scatter magic strings in business code. Use enums or constants.

### 5.2 Data dictionary

PM-Agent needs a data dictionary using two tables:

```text
sys_dict_type       Dictionary category: task_status / risk_level / project_priority
sys_dict_item       Dictionary item: pending / high / p0, etc.
```

Suggested fields for `sys_dict_type`: `id`, `dict_type`, `dict_name`, `system_builtin`, `enabled`, `remark`, `tenant_id`, `created_at`, `updated_at`, `deleted`.

Suggested fields for `sys_dict_item`: `id`, `dict_type`, `dict_code`, `dict_label`, `sort_order`, `color`, `extra_json`, `enabled`, `remark`, `tenant_id`, `created_at`, `updated_at`, `deleted`.

Usage rules:

- Display-oriented fields such as priority and risk category may mainly rely on dictionaries.
- Core state-machine fields such as task status, risk status, and project status use both enums and dictionary display.
- Dictionary codes must not be changed casually because changes affect historical data and business logic.

---

## 6. Core entity scope

| Domain | Typical tables | Phase |
|---|---|---|
| User and permissions | `pm_user`, `pm_role`, `pm_permission`, `pm_user_role` | Phases 1-2 |
| Project | `pm_project`, `pm_project_member` | Phase 1 |
| Requirement | `pm_requirement`, `pm_requirement_change_log` | Phase 2 |
| Task | `pm_task`, `pm_task_dependency`, `pm_task_comment`, `pm_task_status_log` | Phases 1-2 |
| Iteration | `pm_iteration`, `pm_iteration_task` | Phase 2 |
| Risk | `pm_risk`, `pm_risk_event` | Phase 2 / enhanced in Phase 5 |
| Report | `pm_report` | Phase 4 / enhanced in Phase 7 |
| Agent | `agent_trace`, `agent_message`, `agent_tool_call` | Phase 3 |
| Document/RAG | `pm_document`, `document_chunk` | Phase 6 |

Agile Sprint and waterfall phase are both modeled as “迭代 / iteration”. Sprint and phase are glossary synonyms only and must not be used as table names.

---

## 7. Agent Trace data rules

1. Agent Trace tables are separate from business audit logs.
2. Retention is 3 months, with no archive for now.
3. During development and tuning, tool-call inputs, outputs, duration, errors, and model outputs should be stored as completely as practical.
4. Oversized outputs may be truncated; record `truncated=true` and the original size.
5. Sensitive fields must be masked before being stored.
6. Agent Trace is required in Phase 3 and is not deferred together with Phase 7 audit logs.

---

## 8. Data model output format

When designing a data model, use this structure:

```markdown
# 数据模型设计：[模块名称]

## 业务对象关系
（实体之间的关系和边界）

## 术语对齐
（对应 docs/00-术语表.md 中哪些术语）

## 表清单
| 表名 | 说明 | 阶段 |
|---|---|---|

## 表字段设计
（逐表列字段、类型、默认值、是否必填、说明）

## 主键与 ID 策略

## 状态枚举 / 数据字典

## 关键索引
（说明查询场景，不只列索引名）

## 数据约束
（唯一约束、逻辑删除、多租户过滤、软外键策略）

## 日志与追踪
（状态日志、Agent Trace、审计预留）

## 后续扩展点

## 待确认问题
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 9. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Not reserving `tenant_id`;
- Using UUID as an ordinary business primary key;
- Implementing the full RAG document/vector chain in Phases 1-3;
- Changing the primary “迭代 / iteration” term to sprint or phase;
- Replacing string state codes with numeric dictionary values;
- Removing key Agent Trace fields or canceling the 3-month retention period;
- Adding a business table whose concept is not present in the glossary.
