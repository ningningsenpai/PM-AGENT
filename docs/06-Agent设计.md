# Agent 设计

## 1. 运行边界

Agent 与传统业务模块运行在同一个 FastAPI 进程中，但依赖边界保持隔离：

```text
Agent API
  ↓
Agent 编排 / 工具
  ↓ 仅公开 Service
auth / user / project / project_file
  ↓
Repository / Infrastructure
```

Agent、LLM 和 Prompt 不直接获取数据库 Session，不跨模块访问表，也不执行模型生成的 SQL。

## 2. 权限与身份

- `/api/v1/agent/chat` 必须携带 Bearer JWT。
- JWT `sub` 必须与请求体 `user.user_id` 一致。
- 工具执行前由目标模块 Service 再次校验资源归属和状态。
- 删除、权限变更、对外通知等高风险动作必须保留人工确认。
- 写工具需要权限校验、幂等门禁和 Agent Trace。

## 3. Trace

`X-Trace-Id` 从前端进入 FastAPI，并写入统一响应与响应头。Agent 请求中的 `trace_id` 用于现有流式事件兼容；后续应由接入层统一校验两者一致。

建议 Trace 至少记录：

- 用户、项目、会话与轮次；
- 模型提供方、模型名和 token 用量；
- 工具名、结构化参数摘要、执行结果与耗时；
- 人工确认状态；
- 错误码与 traceId。

## 4. 文件解析

项目文件解析是 Python 应用服务，不再是跨 Java/Python HTTP：

1. Service 查询 `active`、尚无有效分析版本且解析次数小于 3 的文件；
2. 通过对象键使用 MinIO SDK 读取；
3. 复用既有解析器、Prompt 和模型适配器；
4. Pydantic 校验输出与文件身份；
5. 写 `system/file_details/*.json`；
6. 条件更新分析投影与解析次数；
7. 从数据库完整生成 `system/index.json`；
8. 将当前有效文件分析投影交给结构化模型生成器，经 Pydantic 校验和稳定 ID 合并后写入 `system/project_specification.json`。

文件详情和项目规范复用同一个结构化 JSON 模型调用组件，具体 Prompt 和 Pydantic 输出模型保持独立。MinIO、LLM 等外部调用位于数据库事务外。单文件分析失败记录错误并继续处理其他候选文件；解析入口可重复调用，以恢复文件级失败或项目规范构建失败。

## 5. 模型与成本

- 模型输出优先使用结构化 JSON。
- 关键输出必须经 Pydantic 或 JSON Schema 校验。
- 模型路由、Prompt 缓存和 token 预算沿用既有 LLM 适配层。
- 禁止把数据库凭据、JWT、预签名地址或敏感文件原文写入 Prompt。
- 本次迁移不扩展完整 RAG、训练或评测能力。
