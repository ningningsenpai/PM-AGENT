---
name: pm-agent-doc-writer
description: Chinese Markdown documentation-writing skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user needs to write or organize requirement documents, technical proposals, API docs, database design docs, module design docs, development plans, README files, deployment guides, or project showcase materials.
metadata:
  status: active
  language: en-US
  owner_module: docs
  related_docs:
    - docs/README.md
    - docs/00-术语表.md
---

# PM-Agent Documentation Writing Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Writing, organizing, or restructuring project documents under `docs/`;
- Producing requirement documents, technical proposals, API specifications, data-model documents, or module design documents;
- Writing README files, deployment instructions, or project showcase / portfolio materials;
- Turning scattered discussion into formal Markdown documents;
- Unifying document structure, heading levels, terminology, acceptance criteria, and pending questions.

## Goal

Help Claude produce Chinese Markdown documentation for PM-Agent that is consistent, clear, maintainable, and useful for solo + AI-assisted development. Documents should support design, implementation, review, and showcase. Avoid empty slogans; documentation must serve development.

---

## 1. Document directory and types

All project documents go under `docs/`.

| Document type | Description |
|---|---|
| Product requirement document | Module goals, users, scope, acceptance criteria |
| Technical proposal | Architecture, layers, APIs, trade-offs, risks |
| API document | Request, response, error codes, permissions, examples |
| Database design document | Tables, fields, indexes, enums, constraints |
| Module design document | Every module must have a design document |
| Agent design document | Prompts, tools, Trace, model strategy |
| Test acceptance document | Manual acceptance, key paths, Agent samples |
| Deployment guide | Environment, startup, configuration, dependencies |
| Project showcase document | Portfolio or external presentation |

A fixed phase-summary template is not required. If a summary is needed later, generate it for the specific phase.

---

## 2. Documentation tools and API documentation strategy

1. API docs need additional Markdown documentation; do not rely only on Knife4j.
2. Knife4j remains an option for API viewing and debugging assistance.
3. API testing should use IDEA built-in plugins or other already installed plugins. Do not force Postman / Apifox in the docs.
4. Every module must have a design document. Complete a minimal design note before code implementation.
5. Documentation style should be formal technical proposal style, not development diary style.

---

## 3. Writing style

1. All documents must use Chinese Markdown.
2. Headings should be clear and stable; avoid excessive nesting.
3. Important designs must explain background, goals, plan, trade-offs, and acceptance criteria.
4. Use tables for fields, APIs, states, and comparisons; do not overuse them.
5. Keep “待确认问题” at the end of each document, but list only questions that truly affect implementation.
6. Do not document historical code details; document current design goals, plans, rules, and acceptance criteria.
7. Terminology must align with `docs/00-术语表.md`.

---

## 4. Standard document structure

Use this structure by default. Adjust by document type when needed, but do not lose background, plan, acceptance criteria, or pending questions.

```markdown
# 文档标题

## 1. 背景
## 2. 目标
## 3. 范围
### 3.1 本期范围
### 3.2 不做范围

## 4. 详细设计
## 5. 开发计划
## 6. 风险与取舍
## 7. 验收标准
## 8. 待确认问题
```

---

## 5. Module design document requirements

Each module design document should include at least:

```markdown
# 模块设计：[模块名称]

## 背景
## 模块职责
## 涉及术语
## 业务流程
## 数据模型
## 接口清单
## 前端页面
## Agent 介入点
## 权限与风险
## 开发步骤
## 验收标准
## 待确认问题
```

---

## 6. API document requirements

API Markdown documents must include:

- API path, including `/api/v1/`;
- Request method;
- Permission requirements;
- Request headers, especially `X-Trace-Id` and `X-Idempotency-Key`;
- Request parameters;
- Response structure;
- Error codes;
- Examples;
- traceId explanation.

---

## 7. Project showcase document requirements

Project showcase / portfolio documents should emphasize:

1. The problem the project solves;
2. Tech stack;
3. Core features;
4. Agent capability highlights;
5. Architecture diagram or flowchart;
6. Demonstration path;
7. Future plan.

Do not exaggerate unfinished capabilities. Mark unimplemented items as planned.

---

## 8. Workflow

1. First confirm the document type and target reader.
2. Check `docs/README.md` and the glossary to confirm naming and directory placement.
3. Read related skills or design documents before writing; avoid generating from imagination.
4. Organize content in formal technical proposal style.
5. After drafting, check for scope, trade-offs, acceptance criteria, and pending questions.
6. If a new business term appears in the document, prompt to update the glossary first.

---

## 9. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Moving project documents out of `docs/`;
- Relying only on Knife4j without maintaining Markdown API docs;
- Adding a module without writing a module design document;
- Writing unimplemented capabilities as completed;
- Conflicting with `pm-agent-backend-architect` logging/API conventions;
- Using terms not present in the glossary.
