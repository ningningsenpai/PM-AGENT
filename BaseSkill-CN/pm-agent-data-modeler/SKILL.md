---
name: pm-agent-data-modeler
description: 面向 PM-Agent 智能项目管理 Agent 平台的数据建模 Skill。每当用户设计数据库表、字段、索引、关系、数据字典、状态枚举、逻辑删除、多租户字段、审计表、Agent Trace 表或判断业务数据如何落到 MySQL/向量库/搜索引擎时，都应使用本 Skill。
metadata:
  status: active
  language: zh-CN
  owner_module: data
  related_docs:
    - docs/00-术语表.md
    - docs/04-数据模型.md
    - docs/06-Agent设计.md
---

# PM-Agent 数据建模 Skill

## 触发场景

当用户提出以下类型请求时使用本 Skill：

- 设计项目、需求、任务、迭代、风险、报告等业务表；
- 设计字段、索引、唯一约束、外键策略、逻辑删除策略；
- 设计状态枚举、数据字典、状态流转日志；
- 设计 Agent Trace、工具调用日志、LLM 消息记录；
- 判断 MySQL、向量库、文件存储、搜索引擎分别存什么；
- 评审数据模型是否支持当前阶段查询、统计和后续扩展。

## 目标

帮助 Claude 为 PM-Agent 设计稳定、可扩展、低返工的数据模型，使业务关系清晰、查询路径明确、Agent 追踪可还原，同时避免第一版过度通用化。

---

## 一、技术基线

| 项 | 选型 / 规则 |
|---|---|
| 主库 | MySQL 8 |
| ORM | MyBatis Plus |
| 删除策略 | 默认逻辑删除；部分大表后续可按日期归档或物理清理 |
| ID 策略 | 性能优先表可用自增；敏感或分布式敏感场景用雪花 ID；除 traceId 外不使用 UUID |
| 状态枚举 | 数据库存字符串 code，不存数字 |
| 多租户 | 所有业务表预留 `tenant_id BIGINT NOT NULL DEFAULT 0` |
| Agent Trace 保留期 | 3 个月，暂不归档 |
| 数据字典 | 需要，便于统一管理 |

---

## 二、核心建模原则

1. 先围绕真实业务关系建模，不为了“通用平台”提前抽象；
2. 表名、字段名、枚举 code 必须遵守 `docs/00-术语表.md`；
3. 状态字段必须配套状态流转日志，方便复盘和 Agent 分析；
4. Agent 相关日志独立建模，不与业务表混写；
5. 索引围绕查询场景设计，不机械给所有字段加索引；
6. 第一版优先保证业务闭环，RAG 文档/向量模型按第 6 阶段设计，不提前实现完整链路。

---

## 三、通用字段规范

### 3.1 BaseEntity 字段

所有业务表默认包含：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT | 主键，自增或雪花，按表策略确定 |
| `tenant_id` | BIGINT NOT NULL DEFAULT 0 | 多租户预留，第 1 阶段固定 0 |
| `created_by` | BIGINT NULL | 创建人 |
| `created_at` | DATETIME NOT NULL | 创建时间 |
| `updated_by` | BIGINT NULL | 更新人 |
| `updated_at` | DATETIME NOT NULL | 更新时间 |
| `deleted` | TINYINT NOT NULL DEFAULT 0 | 逻辑删除标记 |

### 3.2 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| 业务表 | `pm_` 前缀 + 术语英文标识 | `pm_project`、`pm_task`、`pm_iteration` |
| Agent 表 | `agent_` 前缀 | `agent_trace`、`agent_tool_call` |
| 系统表 | `sys_` 前缀 | `sys_dict_type`、`sys_dict_item` |
| 字段 | 小写下划线 | `project_id`、`risk_level` |
| 状态字段 | `status` 或 `{domain}_status` | `status`、`approval_status` |

---

## 四、ID 策略

| 场景 | 策略 | 说明 |
|---|---|---|
| 普通业务主表 | 自增 BIGINT | 简单、性能好，适合单体 MVP |
| 敏感或不希望暴露规模的表 | 雪花 ID | 如 Agent Trace、外部可见报告编号 |
| traceId | UUID 去横线字符串 | 只用于链路追踪，不作为业务主键 |
| 前端临时 key | UUID | 如 `X-Idempotency-Key`，不入业务主键 |

---

## 五、状态枚举与数据字典

### 5.1 状态枚举

1. 数据库存字符串 code，如 `pending`、`in_progress`、`done`；
2. 涉及业务分支的状态必须在 Java / Python 中有枚举约束；
3. 字典表负责展示名称、颜色、排序，不负责决定业务状态机是否合法；
4. 禁止在业务代码中散落魔法字符串，必须通过枚举或常量引用。

### 5.2 数据字典

PM-Agent 需要数据字典，采用双表结构：

```text
sys_dict_type       字典分类：task_status / risk_level / project_priority
sys_dict_item       字典项：pending / high / p0 等
```

`sys_dict_type` 建议字段：`id、dict_type、dict_name、system_builtin、enabled、remark、tenant_id、created_at、updated_at、deleted`。

`sys_dict_item` 建议字段：`id、dict_type、dict_code、dict_label、sort_order、color、extra_json、enabled、remark、tenant_id、created_at、updated_at、deleted`。

使用规则：

- 纯展示类字段（优先级、风险分类等）可主要依赖字典；
- 核心状态机字段（任务状态、风险状态、项目状态）采用“枚举 + 字典展示”双轨；
- 字典 code 禁止随意修改，修改会影响历史数据和业务逻辑。

---

## 六、核心实体范围

| 领域 | 典型表 | 阶段 |
|---|---|---|
| 用户与权限 | `pm_user`、`pm_role`、`pm_permission`、`pm_user_role` | 第 1~2 阶段 |
| 项目 | `pm_project`、`pm_project_member` | 第 1 阶段 |
| 需求 | `pm_requirement`、`pm_requirement_change_log` | 第 2 阶段 |
| 任务 | `pm_task`、`pm_task_dependency`、`pm_task_comment`、`pm_task_status_log` | 第 1~2 阶段 |
| 迭代 | `pm_iteration`、`pm_iteration_task` | 第 2 阶段 |
| 风险 | `pm_risk`、`pm_risk_event` | 第 2 / 第 5 阶段增强 |
| 报告 | `pm_report` | 第 4 / 第 7 阶段增强 |
| Agent | `agent_trace`、`agent_message`、`agent_tool_call` | 第 3 阶段 |
| 文档/RAG | `pm_document`、`document_chunk` | 第 6 阶段 |

> 敏捷 Sprint 与瀑布阶段统一使用“迭代 / iteration”建模；Sprint、阶段只作为术语表同义词，不用于表名。

---

## 七、Agent Trace 数据规则

1. Agent Trace 表独立于业务审计日志；
2. 保留期 3 个月，暂不归档；
3. 开发和调优阶段工具调用入参、出参、耗时、错误、模型输出尽量完整落库；
4. 超大输出可截断并记录 `truncated=true`，后续如引入 MinIO 再外挂保存；
5. 敏感字段必须脱敏后入库；
6. Agent Trace 属于第 3 阶段必做，不随第 7 阶段审计日志延期。

---

## 八、数据模型输出格式

设计数据模型时，按以下结构输出：

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

---

## 九、不可越界

以下事项必须先经用户确认：

- 不预留 `tenant_id`；
- 使用 UUID 作为普通业务主键；
- 把 RAG 文档/向量库完整实现提前到第 1~3 阶段；
- 修改“迭代 / iteration”主术语为 sprint 或 phase；
- 用数字字典替代字符串状态 code；
- 删除 Agent Trace 关键字段或取消 3 个月保留期；
- 新增业务表但术语表中没有对应概念。
