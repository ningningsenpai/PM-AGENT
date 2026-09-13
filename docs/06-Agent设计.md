# PM-Agent Agent 设计

## 1. 产品定位

PM-Agent 是项目分析、进度跟踪和风险提示助手，不承担项目开发执行。它可以读取当前文件、整理项目脉络、核对用户明确设定的项目约束并给出建议，但不能把建议伪装成已完成事项，也不自动创建任务或风险业务实体。

## 2. 存储职责

```text
Vue 3
  → FastAPI 模块化单体
      → MySQL：身份、会话、运行、待确认草稿、报告
      → Redis：JWT 会话、幂等、租约与缓存
      → MinIO：原文件与当前有效上下文快照
      → DeepSeek：语义提取、请求理解与回答
```

MinIO 是项目上下文正文的正式真相源。MySQL 不保存规则、长短期记忆或用户偏好的版本历史。

当前数据库最终结构为 9 张表：

```text
alembic_version
pm_user
pm_project
pm_project_file
agent_conversation
agent_message
agent_run
agent_learning_draft
pm_report
```

## 3. MinIO 上下文资产

```text
system/
├── index.json
├── file_details/*.json
├── project_specification.json
├── project_specification/
│   ├── development_approach.json
│   ├── technical_constraints.json
│   ├── coding_rules.json
│   ├── document_rules.json
│   └── risk_rules.json
├── long_term_memory.json
├── short_term_memory.json
├── user_habits/
│   ├── life.json
│   ├── specification.json
│   ├── thinking.json
│   ├── tooling.json
│   └── work.json
└── update_journal.jsonl
```

### 3.1 原文件、Index 和 Detail

- 原文件：项目当前真实代码和文档；代码反映实现状态，文档可以表达规划和约束。
- Index：导航、文件身份、哈希、Detail 引用与系统资产引用，不承载长篇语义正文。
- Detail：DeepSeek 对单文件的结构化理解，保存摘要、符号、事实、规则候选、原文锚点和解析版本。

### 3.2 项目规则

规则只来自两类来源：合格权威文档中的明确陈述，以及用户在对话中的明确项目级指令。代码只能用于核对规则是否得到遵守，不作为规则来源。

`project_specification.json` 是五个分区的清单，仅保存路径、摘要和条目数。正文按发展方式、技术约束、编码规则、文档规则和风险规则拆分，避免单文件无限膨胀。

规则条目示例：

```json
{
  "id": "稳定规则标识",
  "scope": "project",
  "status": "active",
  "confidence": "high",
  "rule": "所有 Python 代码注释必须使用简体中文",
  "source_refs": [
    {
      "type": "doc",
      "path": "docs/project-plan.md",
      "file_id": 255,
      "content_hash": "sha256",
      "detail_ref": "system/file_details/xxx.json"
    }
  ]
}
```

### 3.3 长短期记忆

- 长期记忆：项目阶段、已完成能力、发展目标、里程碑和已废弃方向。它服务于项目脉络与进度分析，不承担规则、偏好或风险实体职责。
- 短期记忆：当前阶段焦点、对话转折点、待处理事项和仍需复核的信息。它不能覆盖原文件或长期记忆中的已核验事实。

文件分析只写入带当前来源哈希和锚点的可核验事实。对话中的明确目标变更可以更新记忆；不明确表达进入待确认草稿。

### 3.4 项目级用户偏好

用户偏好仅在“用户 + 项目”范围生效，描述回答长度、语气、结构、分析切面和工具使用倾向。它只影响表达和默认选择，不修改业务事实，也不能替代项目规则。

## 4. 项目初始化和更新

### 4.1 初始化顺序

```text
创建项目和 15 个空系统对象
→ 上传原文件并记录身份与哈希
→ 生成初始 Index
→ 对可解析文件调用 DeepSeek 生成 Detail
→ 从合格文档候选确定性重建规则分区
→ 对账长期记忆中的项目事实
→ 重建最终 Index
```

### 4.2 文件更新顺序

```text
计算新增、正文变化、移动和删除
→ 更新文件身份与原文件
→ 只解析新增、正文变化或失败重试文件
→ 更新对应 Detail
→ 对所有当前有效权威文档规则候选做快照对账
→ 对长期事实做来源对账
→ 重建 Index
```

正文未变化时不重复调用模型。纯路径移动更新引用。来源删除或哈希失效后，旧规则和旧事实不得继续进入当前快照。

## 5. 规则更新算法

DeepSeek 只负责每个文档的规则候选提取；跨文件合并由后端确定性执行，不进行第二轮大模型全文总结：

1. 读取全部当前有效且允许提供约束的文档 Detail。
2. 按规则分区转换候选，规范化正文后生成稳定规则 ID。
3. 完全相同的正文合并来源引用，保留更高置信度。
4. 高、中置信度写为 `active`，低置信度写为 `pending_review`。
5. 文件来源规则按当前快照重建；用户或人工规则原样保留。
6. 语义内容未变化时不写对象，避免无意义版本增长。

五个分区先完成 Schema 校验和正文准备，再写入 MinIO，最后刷新清单。清单刷新失败时，系统按写前原始字节回滚已写分区；并发情况下只有对象仍是本次写入版本才允许回滚，避免覆盖其他写入者。

## 6. 对话多维链路

```text
保存用户消息
→ DeepSeek 输出 RequestPlan
→ 后端校验维度、置信度、目标文件与确认策略
→ 明确持久化指令写 MinIO；模糊指令生成待确认草稿
→ 按每个请求单元选择只读工具和召回来源
→ 回读当前原文件或当前上下文条目复核
→ DeepSeek 生成回答
→ 保存回答、运行摘要和 contextUpdate 结果
```

请求理解最小格式：

```json
{
  "schema_version": "2.0",
  "dimensions": [
    {
      "name": "project_progress",
      "confidence": 0.94,
      "evidence_text": "查看当前项目进度"
    },
    {
      "name": "context_update",
      "confidence": 0.91,
      "evidence_text": "以后请给出详细任务提示"
    }
  ],
  "units": [],
  "context_updates": [
    {
      "kind": "preference",
      "target": "user_habits/specification.json",
      "source_text": "以后请给出详细任务提示",
      "confidence": 0.91,
      "explicit": true
    }
  ],
  "requires_clarification": false
}
```

模型输出不能直接操作存储。后端只接受白名单 `kind`、目标分区和动作，并补充可信的用户、项目、消息、ETag、幂等键与 Trace。模型提出的数据库 SQL、任意路径或未注册工具一律不可执行。

## 7. 当前工具白名单

Agent 只注册八个只读工具：

1. `get_current_project`：读取当前项目元数据。
2. `list_current_project_files`：列出当前项目文件。
3. `list_owned_projects`：列出当前用户可访问项目。
4. `retrieve_project_context`：按意图召回当前项目上下文。
5. `list_context_entries`：投影当前上下文条目。
6. `get_context_changes`：读取当前上下文变更。
7. `get_project_report`：读取已有报告。
8. `read_project_file_evidence`：回读当前原文件证据。

上下文更新不是交给模型自由选择的工具调用，而是请求计划经过后端校验后进入专用更新器。当前不注册任务、风险或其他业务写工具。

## 8. 召回设计

当前正式召回采用来源路由加词法评分：

1. 根据请求维度决定检索 Detail、规则、记忆、偏好或报告。
2. 执行路径、稳定 ID、术语归一化和中文字符片段匹配。
3. 对来源分配配额并去除重复候选，不为填满 Top-K 强制返回低相关内容。
4. 规则命中只说明需要核对约束；“实现情况”类问题还必须读取代码证据。
5. 最终引用回查当前文件哈希、路径和行号，旧版本不得进入回答。

基于三组真实快照数据的 A/B 结果：词法 Recall@3=1.0、MRR=1.0；稀疏字符向量 Recall@3=1.0、MRR=0.8333；混合方案与词法打平但复杂度更高。因此保留词法实现，不引入向量数据库。向量化代码仅保存在基准测试目录，不进入生产依赖。

## 9. 失败与一致性

- DeepSeek 失败必须显式返回失败或可识别的降级状态，不得把确定性兜底伪装成真实模型成功。
- MinIO 条件写入使用 ETag；冲突返回可重试或转待确认结果。
- 规则分区与清单的发布失败执行精确字节回滚。
- 用户模糊表达确认前不修改正式快照。
- MySQL 有记录不代表闭环成功；验收必须读取目标 MinIO 对象并校验内容。
- Agent 回答区分原文件事实、上下文事实和模型建议。

## 10. 已暂缓范围

- 任务看板与任务状态机；
- 风险中心与风险处置状态机；
- 向量数据库和生产向量检索；
- 自动执行开发任务；
- 全量上下文历史版本表。

相关能力后续如需恢复，必须重新确认业务边界、数据所有权和验收标准。
