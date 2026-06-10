---
name: pm-agent-cost-optimizer
description: Cost-optimization skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user evaluates LLM call costs, DeepSeek/Claude/GPT model routing, unified model adapters, Prompt caching, token usage, Agent Trace storage cost, vector database cost, deployment cost, local-model extension, or development/runtime budget.
metadata:
  status: active
  language: en-US
  owner_module: cost
  related_docs:
    - docs/06-Agent设计.md
    - docs/02-技术选型.md
    - docs/04-数据模型.md
---

# PM-Agent Cost Optimization Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Evaluating runtime LLM API cost, monthly budget, or call frequency;
- Designing model routing, provider adapters, or degradation strategies;
- Optimizing Prompts, context length, caching, or Trace storage;
- Evaluating vector database, file storage, cloud server, middleware, or deployment cost;
- Deciding whether an Agent capability deserves a high-cost model;
- Planning local models or low-cost models as later extensions.

## Goal

Help Claude control LLM, database, middleware, and deployment cost while preserving PM-Agent’s effectiveness. The plan must fit the reality of solo + AI-assisted development and a runtime monthly budget of about 600 RMB.

---

## 1. Cost boundaries

| Item | Decision |
|---|---|
| Runtime LLM API monthly cost ceiling | About 600 RMB |
| Development-tool cost vs runtime cost | Do not separate before the project is complete; separate later if needed |
| Default low-cost model | Domestic low-cost models are acceptable; choose by model strengths |
| Unified model-provider adapter | Required |
| Local model | Consider later; not part of current development phase |
| Agent Trace Prompt / output | Must be saved, especially natural-language interaction parts |

---

## 2. Model layering strategy

| Scenario | Default model | Upgrade condition |
|---|---|---|
| Intent recognition | DeepSeek | Recognition is unstable or multi-turn context is complex |
| Ordinary project Q&A | DeepSeek | Complex reasoning or important decisions |
| Requirement decomposition | DeepSeek draft | Upgrade to Claude / GPT when decomposition quality is poor |
| Weekly report generation | DeepSeek draft | Final polishing may use a stronger model |
| Risk analysis | DeepSeek / Claude | Critical risk judgments may upgrade |
| RAG Q&A | Refine in Phase 6 | Depends on retrieval quality and context length |

Principle: the default model is not the strongest model. Choose the model based on task value. Use high-cost models only for complex reasoning, final polishing, and key decisions.

---

## 3. Unified model adapter layer

A unified adapter for different model providers is needed, but this does not mean the first version must connect every provider.

### 3.1 Adapter responsibilities

- Unified request parameters: model, messages, temperature, stream, max_tokens;
- Unified response structure: content, usage, finish_reason, error;
- Unified streaming events;
- Unified error retry and degradation;
- Unified cost statistics;
- Unified Trace recording.

### 3.2 Provider integration order

1. First runtime version defaults to DeepSeek.
2. Later, add Claude / GPT / Gemini based on quality and cost needs.
3. OpenAI-compatible API is not a mandatory first requirement; avoid early complexity or cost increase caused by compatibility layers.
4. Local models are reserved as a later offline / low-cost mode.

---

## 4. Caching strategy

Prioritize caching reusable, non-real-time results:

| Scenario | Cache suggestion |
|---|---|
| Weekly report draft | Cache by project + time range + input summary |
| Risk analysis result | Cache by project + data version |
| Document chunk summary | Cache in Phase 6 |
| Prompt templates | Local configuration cache |
| Dictionary / glossary | Cache on both frontend and backend |

Do not cache permission-sensitive results, outputs containing unmasked private data, or high-risk action confirmation results.

---

## 5. Trace storage cost control

1. During development and tuning, keep complete Prompt, model output, and tool-call results.
2. Agent Trace is retained for 3 months by default.
3. Large fields may have thresholds; truncate content beyond the threshold and record `truncated=true`.
4. After MinIO is introduced in Phase 6, very large source text may be stored externally.
5. Sensitive fields must be masked before persistence.
6. Cost estimates must include MySQL storage growth, not only LLM tokens.

---

## 6. Cost evaluation output format

When evaluating cost for a capability or module, use this structure:

```markdown
# 成本评估：[能力/模块名称]

## 调用场景
## 所属阶段
## 成本来源
| 来源 | 说明 | 估算方式 |
|---|---|---|

## 模型选择
## 调用频次估算
## Token / 存储估算
## 缓存策略
## 降级策略
## 质量风险
## 推荐方案
## 后续优化点
## 待确认问题
```

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 7. Workflow

1. First confirm which phase the capability belongs to, avoiding cost engineering for deferred capabilities too early.
2. Clarify call frequency, input length, output length, and whether streaming is involved.
3. Estimate with the default low-cost model first, then evaluate the benefit of stronger models.
4. Identify what can and cannot be cached.
5. Estimate LLM tokens, Trace storage, middleware, and deployment cost together.
6. When recommending a plan, explain quality loss and risk.
7. If cost exceeds the 600 RMB/month runtime budget, provide degradation or rate-limit strategies.

---

## 8. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Changing the default runtime model to a high-cost model;
- Connecting multiple model providers early and making the adapter layer too heavy;
- Including local-model development in the first version;
- Canceling storage of natural-language interaction Prompts / outputs in Agent Trace;
- Ignoring the 600 RMB/month runtime budget;
- Sacrificing key business-decision quality for cost without explaining the risk;
- Treating Phase 6 RAG cost as a mandatory first-version cost.
