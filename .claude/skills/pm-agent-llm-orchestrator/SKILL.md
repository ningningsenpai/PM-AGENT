---
name: pm-agent-llm-orchestrator
description: LLM and Agent orchestration skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user designs the Python Agent service, DeepSeek model calls, model routing, Prompts, streaming output, tool calling, Agent Trace, risk analysis, weekly report generation, Java-Python collaboration, or later RAG planning.
metadata:
  status: active
  language: en-US
  owner_module: agent-service
  related_docs:
    - docs/06-Agent设计.md
    - docs/02-技术选型.md
    - docs/04-数据模型.md
    - docs/05-接口规范.md
---

# PM-Agent LLM Orchestration Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing the Python FastAPI Agent service, model calls, Prompts, or tool calling;
- Designing Agent Q&A, requirement decomposition, weekly report generation, or risk analysis chains;
- Designing Agent Trace, tool-call persistence, or streaming output;
- Designing Java and Python Agent service collaboration;
- Evaluating LLM cost, model routing, or degradation strategy;
- Planning the Phase 6 RAG knowledge base without implementing full RAG early.

## Goal

Help Claude design PM-Agent’s Agent service so model capabilities enter the business system through controlled tool APIs. The result should be traceable, debuggable, cost-controlled, and gated by human confirmation where needed. The Agent handles reasoning and orchestration; the Java backend handles deterministic business logic, permissions, and persistence.

---

## 1. Responsibility split

| Layer | Responsibility |
|---|---|
| Java backend | Business data, permissions, tool APIs, idempotency, unified response, business state logs |
| Python FastAPI | Agent orchestration, Prompts, model calls, streaming output, tool selection, Trace collaboration |
| LLM | Intent recognition, requirement decomposition, report generation, risk explanation, Q&A summary |
| Frontend | Display chat, tool-call process, referenced data, and human-confirmation action cards |

The Agent must not operate the database directly. All business changes must go through Java tool APIs.

---

## 2. Model and cost baseline

| Item | Decision |
|---|---|
| Default runtime model | DeepSeek |
| OpenAI-compatible API | Not required for now to avoid excessive runtime cost |
| Streaming output | Required in the first Agent version |
| Monthly runtime cost ceiling | About 600 RMB |
| RAG | Keep in Phase 6 according to `CLAUDE.md`; do not implement a full RAG chain in the first version |
| Local model | Consider later; not part of the current development phase |

Model strategy:

1. Use DeepSeek by default for intent recognition, ordinary Q&A, and draft generation.
2. Later, upgrade complex reasoning, key decisions, and final polishing to Claude / GPT only after user confirmation.
3. The unified model-provider adapter layer should be defined together by this skill and the cost-optimization skill.
4. Prompts and outputs should be structured where possible. Key business results must be validated with JSON Schema or Pydantic.

---

## 3. Agent capabilities by phase

| Phase | Capability |
|---|---|
| Phase 3 | Agent Q&A, streaming output, Trace, natural-language project queries |
| Phase 4 | Tool calling, requirement-to-task decomposition, weekly report draft generation |
| Phase 5 | Risk analysis, asynchronous tasks, rule + model combination |
| Phase 6 | RAG project knowledge Q&A, document chunking, vector retrieval |

RAG must not be written as a first-version requirement. The first version may reserve interfaces and terminology only; do not introduce a full vector-database chain early.

---

## 4. Tool-calling rules

1. Define deterministic tool APIs first, then let the Agent call them.
2. Each tool must have a clear name, input schema, output schema, permission requirement, and idempotency requirement.
3. When tools call business write APIs, they must carry `X-Trace-Id`, `X-User-Id`, `X-Tenant-Id`, and `X-Idempotency-Key`.
4. When a tool fails, the Agent must not fake success. It must explain the failure to the user and include traceId.
5. Tool results should not be shown to users raw. The Agent should summarize them, while Trace retains debugging information.

---

## 5. Tool-call results and Trace persistence

During development and tuning, tool-call results should be stored completely enough for review and optimization.

### 5.1 Required records

| Content | Description |
|---|---|
| User input | Original user question or instruction |
| Prompt | Main system Prompt / user Prompt / template variables; keep natural-language interaction content complete |
| Model information | provider, model, temperature, token usage |
| Tool calls | tool_name, input_json, output_json, cost_ms, status, error_message |
| Final output | Model final answer or structured result |
| Human confirmation | Whether confirmation is required, confirmer, result, time |
| traceId | Unified with the Java / frontend chain |

### 5.2 Retention policy

- Agent Trace is retained for 3 months, with no archive for now.
- Oversized tool outputs may be truncated; record `truncated=true` and original size.
- Sensitive fields must be masked before persistence.
- In Phase 6, if MinIO is introduced, very large source text may be stored externally with a reference path in the Trace table.

---

## 6. High-risk operations and human confirmation

The following operations require human confirmation. The Agent may only generate suggestions or pending action cards:

1. Deletion / irreversible operations;
2. Permission and member changes;
3. External notification / publishing;
4. Agent-written business changes, including task status updates, risk creation, and generated requirement-decomposition tasks.

Execution mode:

```text
Agent 生成建议 → 前端动作卡片 → 用户确认 → Java 工具 API 执行 → Trace + 状态日志记录
```

---

## 7. Prompt and structured output

### 7.1 Prompt structure

```text
Role and goal
Project context summary
Available tool list
Business constraints and prohibitions
Output format requirements
User input
```

### 7.2 Output requirements

1. Business structured results must be validated with JSON Schema / Pydantic.
2. When information is insufficient, ask follow-up questions. Do not invent projects, tasks, people, or dates.
3. High-risk actions must output `requires_confirmation=true`.
4. User-facing output language is Chinese.
5. Prompt templates should be numbered or named for Trace tracking.

---

## 8. Agent orchestration plan output format

When designing an Agent capability, use this structure:

```markdown
# Agent 编排方案：[能力名称]

## 使用场景
## 所属阶段
## 输入输出
## 模型选择
## Prompt 结构
## 工具清单
| 工具 | 输入 | 输出 | 权限 | 是否幂等 | 是否需人工确认 |
|---|---|---|---|---|---|

## 执行流程
（可用 Mermaid）

## Trace 记录
## 流式输出策略
## 成本控制
## 错误处理
## 验收标准
## 待确认问题
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 9. Workflow

1. First confirm which phase, from Phase 3 to Phase 6, the capability belongs to.
2. If RAG is involved, confirm whether it is only a reserved interface or an official Phase 6 implementation.
3. Define tool APIs before designing the Agent call flow.
4. Define Prompts, structured output schemas, and failure handling.
5. Mark high-risk actions and human-confirmation points.
6. Define Trace fields, persistence strategy, and cost estimate.
7. Output a plan that backend, frontend, and data-modeling work can implement further.

---

## 10. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Implementing full RAG early or introducing a vector database early;
- Bypassing Java tool APIs to operate the database directly;
- Executing high-risk actions without human confirmation;
- Changing the default model from DeepSeek to a high-cost model;
- Connecting an OpenAI-compatible API or adding a new model provider;
- Not recording tool-call results or canceling the 3-month Trace retention period;
- Outputting key business structured results without schema validation.
