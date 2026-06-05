---
name: pm-agent-test-planner
description: Testing-planning skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user designs test strategies, manual acceptance checks, API tests, frontend interaction tests, Agent scenario tests, LLM output samples, regression checks, load tests, or quality gates for PM-Agent.
metadata:
  status: active
  language: en-US
  owner_module: quality
  related_docs:
    - docs/01-开发规划.md
    - docs/05-接口规范.md
---

# PM-Agent Testing Planning Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing module test plans, acceptance cases, or smoke tests;
- Designing backend API tests, frontend interaction tests, or Agent scenario tests;
- Defining whether LLM output meets expectations, or regression examples after Prompt changes;
- Designing load-test scenarios, response checks, or quality gates;
- Deciding whether the current phase needs automated testing, CI, Playwright, or Cypress.

## Goal

Help Claude create practical, lightweight, phase-appropriate testing strategies for PM-Agent. In early development, prioritize manual acceptance and key-path checks. Add automated tests gradually after MVP business logic stabilizes.

---

## 1. Testing strategy baseline

| Item | Decision |
|---|---|
| First-version testing style | Manual acceptance first |
| Automated tests | Add after MVP is complete and business logic is stable |
| Backend testing | Use installed IDE plugins to assist testing |
| Frontend E2E | Do not introduce Playwright / Cypress in v1 |
| Fixed Agent sample set | Needed, but not mandatory early; establish when MVP is stable or development requires it |
| CI process | Not needed in v1 |

---

## 2. Testing scope

| Scope | First-version strategy |
|---|---|
| Java backend APIs | Manual calls + plugin tests; focus on response structure, error codes, traceId, and idempotency |
| Permissions and login | Manually verify login / unauthenticated / unauthorized paths |
| Project / requirement / task / risk | Check state, persistence, and abnormal branches by business flow |
| Vue frontend pages | Manual operation-path acceptance |
| Agent service | First test Prompt effects, tool-call results, and Trace completeness |
| LLM output | Use a small fixed set of samples and human judgment |
| Load testing | Only where needed, such as list queries, Agent calls, or batch tasks |

---

## 3. Required checks after each feature

1. **Business flow check**: run the complete path from entry to result.
2. **Response check**: response structure, error code, traceId, and Chinese message are correct.
3. **Persistence check**: main table, state logs, Trace, and dictionary references match expectations.
4. **Permission check**: unauthenticated / unauthorized / authorized paths.
5. **Idempotency check**: repeated writes with the same `X-Idempotency-Key` do not create duplicate data.
6. **Exception check**: missing parameters, illegal state transitions, and missing resources.
7. **LLM scenario check**: for Agent capabilities, verify expected output, human-confirmation flags, and Trace records.

---

## 4. Manual acceptance case format

```markdown
## 用例：[用例名称]

- 所属模块：
- 前置条件：
- 操作步骤：
  1. 
  2. 
  3. 
- 预期结果：
- 需要检查的数据：
- 异常分支：
- 是否涉及 Agent：是/否
- 是否涉及幂等：是/否
- 是否涉及压测：是/否
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 5. Agent scenario testing

Agent scenario testing should not expect identical wording every time. It should check key structure and business conclusions:

| Check item | Description |
|---|---|
| Intent recognition | Whether the Agent identifies the user's real goal |
| Tool selection | Whether the Agent calls the correct tool |
| Input construction | Whether projectId, taskId, time range, and similar fields are correct |
| Business conclusion | Whether risk level, task decomposition, and weekly-report summaries are reasonable |
| Human confirmation | Whether high-risk actions are marked as requiring confirmation |
| Trace | Whether Prompt, tool calls, and model output are persisted |

After the MVP stabilizes, establish a fixed sample set covering project Q&A, requirement decomposition, risk detection, weekly report generation, and tool failure.

---

## 6. Test plan output format

When designing a test plan, use this structure:

```markdown
# 测试方案：[模块名称]

## 测试目标
## 测试范围
## 不测范围
## 测试数据
## 手动验收用例
## 接口测试用例
## 前端交互用例
## Agent 场景用例
## 异常与边界场景
## 幂等检查
## 压测检查（如需要）
## 回归检查点
## 验收标准
## 待确认问题
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 7. Workflow

1. First identify which phase the module belongs to, avoiding a heavy testing system too early.
2. In the first version, prioritize manual acceptance cases and do not force automation.
3. Every business module should cover normal paths, abnormal paths, permission paths, and idempotency paths.
4. Agent capabilities must cover tool calls, Trace, and human confirmation.
5. Plan Playwright / Cypress / CI only when the user explicitly asks or the business is stable.
6. Load testing should target scenarios with clear performance risk, not every API by default.

---

## 8. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Introducing CI in the first version;
- Introducing Playwright / Cypress in the first version;
- Requiring automated tests for every Controller / Service;
- Blocking MVP delivery for coverage percentage;
- Testing Agent output only by wording while ignoring tool calls and Trace;
- Expanding load testing to all APIs.
