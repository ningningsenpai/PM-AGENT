# Chat 模块分层设计

> 本文记录 2026-09-08 初次分层重构的历史基线。2026-09-09 已确认：显式学习只负责候选审核，正式上下文仍写入 MinIO `system/` 固定文件；版本清单和快照重发不再属于目标设计。当前目标以 [第 27 篇](./27-云端上下文与显式学习改造.md) 为准。

## 1. 目标与职责

Chat 为 PM 助手提供会话、消息、显式学习、上下文管理及运行记录。按业务职责拆分子包，使接口、校验和持久化实现具有明确归属。运行栈保持 FastAPI 模块化单体，业务表仍由 Python 写入、Alembic 管理。

会话指项目内持久保存的问答历史；显式学习从用户新消息提取候选内容；上下文条目保存词条、习惯和长短期记忆；运行记录保存幂等键、模型与工具 Trace、状态和结果。前端使用 PM 助手的项目问答、学习内容管理及运行详情，报告页面通过报告模块复用上下文和运行服务。

## 2. 目录与归属

```text
app/modules/chat/
├── __init__.py                 # 公开项目初始化服务
├── api.py                      # 路由聚合
├── dependencies.py             # 公开服务与请求级依赖装配
├── _persistence.py             # ID 类型及不提交事务的仓储基础操作
├── conversation/
│   ├── api.py                  # 会话、消息、当前会话工具目录
│   ├── schemas.py
│   ├── service.py
│   ├── repository.py
│   └── models.py
├── learning/
│   ├── api.py
│   ├── schemas.py              # 模型候选约束
│   ├── service.py              # 读取消息、调用模型、应用候选、推进游标
│   ├── rules.py                # 来源、归属、版本和确认规则
│   └── prompts.py
├── context/
│   ├── api.py
│   ├── schemas.py              # 条目类型与纠正契约
│   ├── service.py
│   ├── repository.py
│   ├── models.py
│   ├── serialization.py        # 日期和条目视图转换
│   ├── snapshot.py             # 历史快照实现，目标设计中移除
│   ├── initialization.py
│   ├── lexicon.py              # 学习词条匹配适配
│   └── documents/             # 初始化文件格式
│       ├── short_term_memory.py
│       ├── long_term_memory.py
│       └── user_habits.py
├── runs/
│   ├── api.py
│   ├── service.py
│   ├── repository.py
│   └── models.py
└── legacy/
    └── api.py                  # 原无状态问答协议
```

学习没有独立业务表，不创建自己的 Model 和 Repository。文件初始化契约与 MySQL 学习条目分别维护，不能把初始化空文件的结构当成条目管理接口。

报告拥有 `app/modules/report/schemas.py` 和 `dependencies.py`。共用的严格字段别名规则位于 `app/core/schemas.py`，结构化生成器装配位于 `app/llm/dependencies.py`。报告不会通过 Chat 获取自己的模型输出结构或服务工厂。

## 3. 数据模型与依赖方向

| 子包 | 实体表 | 数据访问 |
|---|---|---|
| conversation | agent_conversation、agent_message | ConversationRepository |
| context | agent_context_scope、agent_context_entry、agent_context_change | ContextRepository |
| runs | agent_run | RunRepository |
| report | pm_report | 报告模块自己的 ReportRepository |

ORM 类在各自子包中只有一份定义，由数据库 `model_registry.py` 集中导入供 Alembic 收集。表名、字段类型、索引、外键和默认值保持既有定义；本次没有数据库迁移。

依赖方向为 `API → Service → Repository / 基础设施`。API 不访问数据库和存储客户端；模型工具仅接收公开业务 Service。各 Repository 独立执行 SQL，不调用其他 Repository。会话消息查询通过 SQL 关联运行表取得 requestKey，不向运行仓储转发查询。

跨 Chat 子包的业务协作由 Service 编排。学习服务使用上下文仓储和会话仓储，运行服务使用运行仓储和会话仓储；依赖装配确保这些仓储共用一个请求级 Session。包之间的拆分不等同于事务之间的拆分。报告与文件解析通过 `chat.dependencies.get_run_service` 获取运行服务，不直接构造 Chat 仓储。

`runs` 暂留 Chat 内：它同时负责通用运行记录与会话租约。以后若提升为独立模块，需先明确会话租约归属，再调整依赖。

## 4. 业务与事务流程

| 用例 | 提交和外部调用边界 |
|---|---|
| 新建会话 | 作用域锁、自动编号与会话写入位于同一事务 |
| 发送消息 | 幂等运行与租约提交后保存用户消息；释放事务后调用 Agent；回答、运行结果及租约释放共同提交 |
| 显式学习 | 读取消息与当前固定上下文后释放事务，再调用模型；候选、反馈、学习游标和运行结果作为工作流数据保存 |
| 学习失败 | 保留已持久化草稿和反馈，保存失败运行并释放租约；正式上下文不发生变化 |
| 用户确认 | 固定确认计划后释放事务，按目标文件执行 ETag 条件覆盖；保存各目标结果，失败项可按原幂等操作恢复 |
| 取消或租约过期 | 保留失败运行，释放原会话占用；同幂等键仍关联原运行，后续显式请求使用新键 |

`learning/rules.py` 只执行候选规则，`learning/prompts.py` 保持既有学习 Prompt 及版本。内容入站、证据核对、显式确认、过期内容和版本冲突的现有行为保持不变。学习不会自动执行任务、风险等业务写动作。

## 5. 接口与兼容

根 `chat/api.py` 统一注册会话、学习、上下文、运行及旧协议接口。URL、HTTP 方法、请求头、参数、响应体、业务码及鉴权约定见 [接口规范第 9 节](./05-接口规范.md#9-持久化项目助手闭环)。报告仍使用 `/api/v1/projects/{projectId}/reports`。

旧 `/api/v1/agent/chat` 保持无状态问答；持久化问答仍使用普通 HTTP，会话历史由后端读取，不开放客户端工具协议注入。所有权由 JWT 身份与项目归属校验，问答、学习和报告继续使用既有幂等键。未新增模型工具、流式接口或中间件。

项目创建继续通过 `from app.modules.chat import ChatContextInitializationService` 使用初始化服务。初始化对象路径及文件结构保持一致。在线代码及测试改为引用职责子包；`app.normalization` 的既有兼容符号保持不变。

## 6. 验收与限制

2026-09-08 完成以下验证：

- 全部后端单元测试 334 项通过，使用确定性模型样例与测试基础设施。
- 完整 OpenAPI 的 27 个路径及组件结构与重构前一致。
- 注册的 10 张业务表生成的 MySQL 建表语句及索引与重构前一致。
- 新增路由聚合、依赖方向、共享请求 Session、学习中途失败回滚、模型调用前事务释放、过期租约恢复检查。
- 该轮曾验证学习版本和快照失败重发；这部分只作为历史证据，不代表修正后的固定文件方案已经完成验收。

单元测试使用 SQLite，不代表已完成 MySQL 多连接并发锁验证；没有调用真实模型或修改在线业务数据。结构对比不执行 Alembic 迁移。

复核命令：在 `agent-service` 目录执行 `python -m pytest tests/unit -q`。测试目录必须允许当前进程创建、读取和清理临时文件；不要将临时目录权限错误当成业务测试失败。

## 7. 待确认问题

暂无影响本次实施的问题。独立运行模块与 MySQL 并发专项验收可按后续需求安排。
