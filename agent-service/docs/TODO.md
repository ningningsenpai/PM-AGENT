# TODO List

## 当前工作
- 完善归纳agent输入和输出payload的格式：
- 统一规范参数和输入信息的校验（使用@model_validator或者统一在validator中处理）

## 接入层

### P1

1. 新增统一 `AgentContext`，承载 `trace_id`、`user_id`、`tenant_id`、`conversation_id`、`scene`、`source`、`idempotency_key` 等上下文字段。
2. 完善请求 Schema，补充 `scene`、`enable_tools`、`enable_rag`、`metadata` 等扩展字段。
3. 统一错误结构，补齐 Agent 参数错误、模型调用失败、工具调用失败、上下文构建失败等 `4xxxx` 错误码。
4. 完善 SSE 异常事件，确保流式输出中途失败时返回 `event: error`，并携带 `code`、`message`、`traceId`。
5. 清理 `ProjectChatAgent` 中的临时 `print`，替换为正式日志，避免直接打印敏感 Prompt。

### P2

1. 新增 Agent 场景路由，先支持 `project_chat`，后续扩展 `requirement_decompose`、`weekly_report`、`risk_analysis`。
2. 抽象 `BaseAgent` 或 Agent 协议，统一 `chat()` 和 `stream_chat()` 接口。
3. 预留 Trace 数据结构，记录用户输入、Prompt 快照、模型信息、token 用量、工具调用、最终输出和异常信息。
4. 梳理 Prompt 模板管理，增加 Prompt 名称、版本、场景和输出要求，便于后续 Trace 追踪。

### P3

1. 补充接入层验收样例，包括非流式对话、SSE 对话、多轮历史、traceId 返回、异常响应等。
2. 完善客户端断开、usage 缺失等边界场景处理。

## Agent 编排层

### 多轮次对话

#### P1

1. 完善对话迭代算法，增强上下文构建策略。
2. 按 token 预算裁剪上下文，避免只按轮次保留导致长消息超限。
3. 明确多个 system message 的处理策略。
4. 明确工具调用结果进入上下文的格式。

#### P2

1. 优化上下文压缩摘要格式，降低摘要被模型误解为新 assistant 回复的风险。
2. 上下文构建失败时返回明确错误，而不是透传底层异常。

#### P3

1. 完善 Java 模块之后重新审查设计该模块数据结构字段的 default 值。

### 工具调用

#### P1

1. 完善工具调用算法，增加工具调用策略。（`ProjectChatAgent` 文件为调用入口）
2. 明确 Demo 工具仅用于本地开发和链路验证。
3. 将工具触发逻辑从关键词判断升级为更明确的策略判断。

#### P2

1. 固定工具调用结果结构，便于 Agent 摘要和 Trace 记录。
2. 工具失败时返回结构化错误，Agent 不伪造成功结果。

#### P3

1. 后续与 Java 工具 API 联调前，再统一工具请求 Header、超时和幂等策略。

## LLM 调用层

### P1

1. 封装模型调用异常，避免底层 provider 异常直接抛到接口层。
2. 增加模型调用超时处理。
3. provider 不存在、默认模型配置缺失时返回明确错误。
4. token 超限时返回明确错误，并携带 traceId。

### P2

1. 统一非流式和流式模型返回结构。
2. 完善 `usage` 为空时的兼容处理。
3. 记录模型 provider、model、temperature、token 用量和耗时，供 Trace 使用。

## 测试与验收

### P1

1. 增加普通非流式对话验收样例。
2. 增加 SSE 流式对话验收样例。
3. 增加多轮历史对话验收样例。
4. 增加上下文超长触发压缩的验收样例。
5. 增加 provider 不存在、模型调用失败、上下文构建失败的异常样例。

### P2

1. 增加 Demo 工具触发和工具失败样例。
2. 增加 usage 统计返回样例。
3. 增加 Prompt 版本和 Trace 预留字段检查样例。
