---
name: pm-agent-llm-orchestrator
description: 面向 PM-Agent 智能项目管理 Agent 平台的 LLM 与 Agent 编排 Skill。每当用户设计 Python Agent 服务、DeepSeek 模型调用、模型路由、Prompt、流式输出、工具调用、Agent Trace、风险分析、周报生成、Java 与 Python 协作或 RAG 后续方案时，都应使用本 Skill。
metadata:
  status: active
  language: zh-CN
  owner_module: agent-service
  related_docs:
    - docs/06-Agent设计.md
    - docs/07-成本控制.md
    - docs/05-接口规范.md
---

# PM-Agent LLM 编排 Skill

## 触发场景

当用户提出以下类型请求时使用本 Skill：

- 设计 Python FastAPI Agent 服务、模型调用、Prompt、工具调用；
- 设计 Agent 问答、需求拆解、周报生成、风险分析链路；
- 设计 Agent Trace、工具调用落库、流式输出；
- 设计 Java 与 Python Agent 服务协作；
- 评估 LLM 成本、模型路由、降级策略；
- 规划第 6 阶段 RAG 知识库，但不提前实现完整 RAG。

## 目标

帮助 Claude 设计 PM-Agent 的 Agent 服务，使模型能力通过受控工具 API 进入业务系统，做到可追踪、可调试、可控成本、可人工确认。Agent 负责推理与编排，Java 后端负责确定性业务、权限和数据落库。

---

## 一、职责划分

| 层 | 职责 |
|---|---|
| Java 后端 | 业务数据、权限、工具 API、幂等、统一响应、业务状态日志 |
| Python FastAPI | Agent 编排、Prompt、模型调用、流式输出、工具选择、Trace 写入协作 |
| LLM | 意图识别、需求拆解、报告生成、风险解释、问答总结 |
| 前端 | 展示对话、工具调用过程、引用数据、人工确认动作卡片 |

Agent 禁止直接操作数据库。所有业务变更必须通过 Java 工具 API。

---

## 二、模型与成本基线

| 项 | 决策 |
|---|---|
| 默认运行时模型 | DeepSeek |
| OpenAI-compatible API | 暂不要求兼容，避免运行成本过高 |
| 流式输出 | 第一版 Agent 必须支持 |
| 月度运行成本上限 | 约 600 元人民币 |
| RAG | 按 CLAUDE.md 原规划放第 6 阶段，不提前到第一版完整实现 |
| 本地模型 | 后续扩展考虑，不纳入当前开发阶段 |

模型策略：

1. 默认用 DeepSeek 承担意图识别、普通问答、草稿生成；
2. 复杂推理、关键决策、最终润色可后续升级到 Claude / GPT，但需经过用户确认；
3. 模型供应商统一适配层由成本优化 Skill 与本 Skill 协同定义；
4. Prompt 和输出尽量结构化，关键业务结果必须用 JSON Schema 或 Pydantic 校验。

---

## 三、Agent 核心能力分阶段

| 阶段 | 能力 |
|---|---|
| 第 3 阶段 | Agent 问答、流式输出、Trace、项目自然语言查询 |
| 第 4 阶段 | 工具调用、需求拆解任务、周报草稿生成 |
| 第 5 阶段 | 风险分析、异步任务、规则与模型结合 |
| 第 6 阶段 | RAG 项目知识问答、文档切片、向量检索 |

> RAG 不能提前写成第一版必做；第一版最多预留接口和术语，不引入完整向量库链路。

---

## 四、工具调用规则

1. 先定义确定性工具 API，再让 Agent 调用；
2. 工具必须有明确名称、输入 schema、输出 schema、权限要求、幂等要求；
3. 工具调用业务写接口时必须携带 `X-Trace-Id`、`X-User-Id`、`X-Tenant-Id`、`X-Idempotency-Key`；
4. 工具失败时，Agent 不得伪造成功结果，必须向用户说明失败并给出 traceId；
5. 工具返回结果不直接原样展示给用户，需由 Agent 总结，但 Trace 中保留调试信息。

---

## 五、工具调用结果与 Trace 落库

开发与调优阶段，工具调用结果需要完整落库，便于复盘和调优。

### 5.1 必须记录的内容

| 内容 | 说明 |
|---|---|
| 用户输入 | 用户原始问题或指令 |
| Prompt | 主要系统 Prompt / 用户 Prompt / 模板变量；自然语言交互部分需保留完整内容 |
| 模型信息 | provider、model、temperature、token 用量 |
| 工具调用 | tool_name、input_json、output_json、cost_ms、status、error_message |
| 最终输出 | 模型最终回答或结构化结果 |
| 人工确认 | 是否需要确认、确认人、确认结果、确认时间 |
| traceId | 与 Java / 前端链路统一 |

### 5.2 保留策略

- Agent Trace 保留 3 个月，暂不归档；
- 工具输出过大时可截断，并记录 `truncated=true` 和原始大小；
- 敏感字段必须脱敏后入库；
- 第 6 阶段如引入 MinIO，可将超大原文外挂存储，Trace 表保存引用路径。

---

## 六、高风险操作与人工确认

以下操作必须人工确认，Agent 只能生成建议或待确认动作卡片：

1. 删除 / 不可逆操作；
2. 权限与成员变更；
3. 对外通知 / 发布；
4. Agent 自动写业务，包括修改任务状态、创建风险、生成并采纳拆解任务等。

执行模式：

```text
Agent 生成建议 → 前端动作卡片 → 用户确认 → Java 工具 API 执行 → Trace + 状态日志记录
```

---

## 七、Prompt 与结构化输出

### 7.1 Prompt 结构

```text
角色与目标
项目上下文摘要
可用工具清单
业务约束与禁止事项
输出格式要求
用户输入
```

### 7.2 输出要求

1. 业务结构化结果使用 JSON Schema / Pydantic 校验；
2. 信息不足时必须追问，不得编造项目、任务、人员、时间；
3. 对高风险动作输出 `requires_confirmation=true`；
4. 输出给用户的语言统一中文；
5. Prompt 模板应编号或命名，便于 Trace 追踪。

---

## 八、Agent 编排方案输出格式

设计 Agent 能力时，按以下结构输出：

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

---

## 九、工作流程

1. 先确认能力属于第 3~6 阶段中的哪个阶段；
2. 若涉及 RAG，确认是否只是预留还是第 6 阶段正式实现；
3. 定义工具 API，再设计 Agent 调用流程；
4. 定义 Prompt、结构化输出 schema 和失败处理；
5. 标出高风险动作和人工确认点；
6. 定义 Trace 字段、落库策略和成本估算；
7. 输出可交给后端、前端、数据模型继续实现的方案。

---

## 十、不可越界

以下事项必须先经用户确认：

- 提前实现完整 RAG 或引入向量库；
- 绕过 Java 工具 API 直接操作数据库；
- 高风险动作不经人工确认直接执行；
- 默认模型从 DeepSeek 改为高成本模型；
- 接入 OpenAI-compatible API 或新增模型供应商；
- 不记录工具调用结果或取消 3 个月 Trace 保留；
- 输出未经 schema 校验的关键业务结构化结果。
