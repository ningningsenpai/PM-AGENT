# Agent 服务展示数据与最小接口设计

> 文档状态：接口与数据边界设计稿  
> 适用范围：PM-Agent 当前 Figma 终稿中的项目初始化、项目简报、风险候选、任务拆解和 PM 助手  
> 更新时间：2026-07-11

## 1. 核心结论

整个系统的页面展示并不是大多数数据都由 `agent-service` 直接提供。

正确的数据边界是：

| 数据类型 | 唯一事实源 | `agent-service` 职责 |
|---|---|---|
| 用户、项目、任务、风险状态、任务数量、截止日期 | Java 后端与 MySQL | 通过 Java 工具接口读取，不直接访问数据库 |
| 项目文件和文件索引 | Java 管理的项目资料记录、MinIO、项目上下文索引 | 扫描、解析、识别技术栈和模块边界 |
| 风险候选 | Java 保存的 `pm_risk` 草稿记录 | 生成候选、原因、证据和处理建议 |
| 任务拆解草稿 | Java 保存的 `pm_task_draft` | 生成任务草稿，不直接创建正式任务 |
| 项目进度简报 | Java 保存的 `pm_project_brief` | 基于业务快照生成自然语言总结和建议 |
| 对话和模型执行信息 | Java 保存的会话、Trace、工具调用记录 | 负责模型调用、工具编排和流式事件生成 |

因此：

1. 项目总数、任务总数、延期数、阻塞数、完成率等确定性统计由 Java 聚合；
2. `agent-service` 只提供文件解析结果、项目简报、风险候选、任务草稿、对话回答和模型执行元数据；
3. Agent 输出的风险和任务只能作为草稿，必须由用户确认后通过 Java 业务接口写入正式业务表；
4. 本文提到的 MySQL 表均由 Java 后端负责读写，`agent-service` 不直接连接业务数据库；
5. `agent-service` 返回结构化结果，由 Java 完成权限校验、持久化和面向前端的聚合。

## 2. 最少接口数量

最少需要 **3 个 Agent 接口**。

| 序号 | 方法 | 接口 | 作用 |
|---|---|---|---|
| 1 | `POST` | `/api/v1/agent/jobs` | 创建项目初始化、项目简报、风险分析或任务拆解作业 |
| 2 | `GET` | `/api/v1/agent/jobs/{jobId}` | 查询作业进度、阶段状态、错误和最终结构化结果 |
| 3 | `POST` | `/api/v1/agent/chat` | 提供 PM 助手普通或流式对话 |

`POST /api/v1/agent/jobs` 通过受控枚举 `jobType` 区分能力：

| `jobType` | 能力 |
|---|---|
| `project_initialization` | 扫描项目文件、识别技术栈、模块边界并生成初始化结果 |
| `project_summary` | 生成项目进度简报 |
| `risk_analysis` | 生成风险候选 |
| `task_decomposition` | 生成任务拆解草稿 |

不建议为每种 Agent 能力各设计一套“创建、进度、结果”接口，否则至少会扩展为 8 个接口，并造成作业状态、错误结构和 Trace 字段重复。

现有的以下接口不计入上述 3 个展示接口：

- `POST /api/v1/project/files/build`
- `POST /api/v1/project/files/update-tree`
- `/api/v1/minio/files/*`

这些接口属于项目文件采集和对象存储能力，应由统一 Agent 作业内部调用，不应由前端直接调用。

## 3. 通用作业数据结构

所有 Agent 作业都必须返回以下公共字段。

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `jobId` | `pm_project_analysis_job.external_job_id` | Agent 作业唯一标识 |
| `jobType` | `pm_project_analysis_job.job_type` | 作业类型 |
| `projectId` | `pm_project_analysis_job.project_id`，关联 `pm_project.id` | 作业所属项目 |
| `sourceVersionId` | `pm_project_analysis_job.source_version_id`，关联 `pm_project_source.id` | 本次分析使用的项目资料版本 |
| `status` | `pm_project_analysis_job.status` | `pending/running/success/failed/cancelled` |
| `progressPercent` | `pm_project_analysis_job.progress_percent` | 作业整体进度，范围为 0 到 100 |
| `currentStage` | `pm_project_analysis_job.current_stage` | 当前执行阶段编码 |
| `stages` | `pm_project_analysis_job.stage_json` | 各阶段进度和状态列表 |
| `resultType` | `pm_project_analysis_job.result_type` | 最终结果结构类型 |
| `result` | `pm_project_analysis_job.result_json` | 按 `jobType` 返回的结构化结果 |
| `errorCode` | `pm_project_analysis_job.error_code` | 失败错误码 |
| `errorMessage` | `pm_project_analysis_job.error_message` | 中文失败原因 |
| `modelProvider` | `agent_trace.provider` | 实际模型提供方 |
| `model` | `agent_trace.model` | 实际模型名称 |
| `inputTokens` | `agent_trace.input_tokens` | 本次作业输入 Token 数 |
| `outputTokens` | `agent_trace.output_tokens` | 本次作业输出 Token 数 |
| `totalTokens` | `agent_trace.total_tokens` | 本次作业总 Token 数 |
| `startedAt` | `pm_project_analysis_job.started_at` | 作业开始时间 |
| `finishedAt` | `pm_project_analysis_job.finished_at` | 作业结束时间 |
| `traceId` | `pm_project_analysis_job.trace_id`，关联 `agent_trace.trace_id` | 前端、Java、Agent 和模型调用链标识 |

`stages` 中每个元素包含：

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `stageCode` | `pm_project_analysis_job.stage_json` | 阶段编码 |
| `stageName` | `pm_project_analysis_job.stage_json` | 中文阶段名称 |
| `status` | `pm_project_analysis_job.stage_json` | `waiting/running/success/failed` |
| `progressPercent` | `pm_project_analysis_job.stage_json` | 阶段进度 |
| `message` | `pm_project_analysis_job.stage_json` | 页面展示的中文执行说明 |

---

## 4. 模块 1：项目初始化与解析

### 数据库表

| 表名 | 所属服务 | 作用 | 当前状态 |
|---|---|---|---|
| `pm_project` | Java | 项目基础信息 | 已存在 |
| `pm_project_source` | Java | 项目资料版本、来源和导入状态 | 待新增 |
| `pm_project_file` | Java | 项目文件元数据和存储引用 | 待新增 |
| `pm_project_analysis_job` | Java | 初始化与分析作业状态 | 待新增 |
| `agent_trace` | Java | 模型调用、Prompt、Token 和 Trace | 待新增 |
| `index.json` | MinIO 或受控文件存储 | 项目上下文轻量索引，不是 MySQL 表 | 待基于 Java 文件事件实现 |

### 需要展示的数据字段

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `projectId` | `pm_project.id` | 项目 ID |
| `projectName` | `pm_project.name` | 初始化页面展示的项目名称 |
| `projectStatus` | `pm_project.status` | 项目当前业务状态 |
| `jobId` | `pm_project_analysis_job.external_job_id` | 当前初始化作业 ID |
| `analysisStatus` | `pm_project_analysis_job.status` | 初始化整体状态 |
| `progressPercent` | `pm_project_analysis_job.progress_percent` | 初始化总体进度 |
| `currentStage` | `pm_project_analysis_job.current_stage` | 当前阶段 |
| `stages[].stageCode` | `pm_project_analysis_job.stage_json` | 阶段编码 |
| `stages[].stageName` | `pm_project_analysis_job.stage_json` | 阶段名称，例如“读取项目文件结构” |
| `stages[].status` | `pm_project_analysis_job.stage_json` | 阶段状态 |
| `stages[].progressPercent` | `pm_project_analysis_job.stage_json` | 阶段进度 |
| `stages[].message` | `pm_project_analysis_job.stage_json` | 阶段说明或失败原因 |
| `sourceVersionId` | `pm_project_source.id` | 项目资料版本 ID |
| `sourceVersionNo` | `pm_project_source.version_no` | 项目资料版本号 |
| `sourceName` | `pm_project_source.source_name` | 用户选择的文件夹、压缩包或仓库名称 |
| `sourceType` | `pm_project_source.source_type` | `folder_upload/zip/git/local_workspace` |
| `fileCount` | `pm_project_source.file_count` | 纳入项目上下文的文件数 |
| `directoryCount` | `pm_project_source.directory_count` | 目录数量 |
| `ignoredFileCount` | `pm_project_source.ignored_file_count` | 被过滤的文件数 |
| `totalSizeBytes` | `pm_project_source.total_size_bytes` | 项目资料总大小 |
| `files[].fileId` | `pm_project_file.id` | 项目文件记录 ID |
| `files[].relativePath` | `pm_project_file.relative_path` | 文件在项目中的相对路径 |
| `files[].fileName` | `pm_project_file.file_name` | 文件名 |
| `files[].language` | `pm_project_file.language` | 识别出的语言 |
| `files[].module` | `pm_project_file.module_name` | 文件所属模块 |
| `files[].scanStatus` | `pm_project_file.scan_status` | 文件扫描状态 |
| `files[].ignoreReason` | `pm_project_file.ignore_reason` | 被忽略原因 |
| `files[].contentHash` | `pm_project_file.content_hash` | 内容哈希，用于增量更新 |
| `files[].storagePath` | `pm_project_file.storage_path` | MinIO 或受控存储中的对象路径 |
| `scanSummary.totalNodes` | `pm_project_analysis_job.result_json` | 扫描节点总数 |
| `scanSummary.hashedFiles` | `pm_project_analysis_job.result_json` | 已计算内容哈希的文件数 |
| `scanSummary.skippedFiles` | `pm_project_analysis_job.result_json` | 跳过处理的文件数 |
| `techStacks[].name` | `pm_project_analysis_job.result_json` | 技术栈名称，例如 Vue、Spring Boot |
| `techStacks[].version` | `pm_project_analysis_job.result_json` | 识别到的版本，无法确定时为空 |
| `techStacks[].confidence` | `pm_project_analysis_job.result_json` | 识别置信度 |
| `techStacks[].evidencePaths` | `pm_project_analysis_job.result_json` | 支撑识别结论的文件路径 |
| `modules[].name` | `pm_project_analysis_job.result_json` | 模块名称 |
| `modules[].path` | `pm_project_analysis_job.result_json` | 模块根路径 |
| `modules[].type` | `pm_project_analysis_job.result_json` | 模块类型，例如 frontend/backend/agent |
| `modules[].description` | `pm_project_analysis_job.result_json` | 模块职责摘要 |
| `generatedAt` | `pm_project_analysis_job.finished_at` | 初始化结果生成时间 |
| `traceId` | `pm_project_analysis_job.trace_id` | 初始化调用链标识 |
| `errorCode` | `pm_project_analysis_job.error_code` | 初始化失败错误码 |
| `errorMessage` | `pm_project_analysis_job.error_message` | 初始化失败中文说明 |

### 接口

#### `POST /api/v1/agent/jobs`

- `jobType=project_initialization`；
- 绑定 `pm_project`、`pm_project_source`、`pm_project_file`；
- Java 传入项目 ID、资料版本、可读取的文件引用和项目基础信息；
- Agent 返回 `jobId`、初始状态、阶段列表和 `traceId`；
- Java 将作业信息写入 `pm_project_analysis_job`。

#### `GET /api/v1/agent/jobs/{jobId}`

- 返回 `pm_project_analysis_job` 对应的进度字段；
- 成功后返回文件统计、技术栈和模块识别结果；
- Java 将最终结果持久化并提供给项目初始化页和项目管理页。

---

## 5. 模块 2：项目进度简报

### 数据库表

| 表名 | 所属服务 | 作用 | 当前状态 |
|---|---|---|---|
| `pm_project` | Java | 项目基础信息 | 已存在 |
| `pm_task` | Java | 任务事实数据 | 已存在 |
| `pm_task_status_log` | Java | 任务状态变化 | 已存在 |
| `pm_risk` | Java | 项目风险 | 待新增 |
| `pm_project_activity` | Java | 项目近期活动 | 待新增 |
| `pm_project_brief` | Java | Agent 生成的项目简报 | 待新增 |
| `agent_trace` | Java | 简报生成 Trace | 待新增 |

### 需要展示的数据字段

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `briefId` | `pm_project_brief.id` | 简报记录 ID |
| `projectId` | `pm_project.id` | 所属项目 ID |
| `projectName` | `pm_project.name` | 项目名称 |
| `projectStatus` | `pm_project.status` | 项目状态 |
| `summary` | `pm_project_brief.summary` | 项目当前状态的一句话摘要 |
| `healthStatus` | `pm_project_brief.health_status` | `healthy/attention/delayed/blocked` |
| `developmentReview` | `pm_project_brief.development_review_json` | 开发回顾条目列表 |
| `iterationInfo` | `pm_project_brief.iteration_info_json` | 当前阶段或迭代说明条目列表 |
| `recommendations` | `pm_project_brief.recommendation_json` | 下一步开发建议列表 |
| `missingData` | `pm_project_brief.missing_data_json` | 数据不足或需要补齐的内容 |
| `sourceReferences` | `pm_project_brief.source_reference_json` | 生成简报时引用的项目、任务、风险和活动标识 |
| `taskTotal` | `pm_task` 聚合 | 项目任务总数，由 Java 计算后作为 Agent 输入 |
| `taskDoneTotal` | `pm_task.status` 聚合 | 已完成任务数，由 Java 计算 |
| `taskOverdueTotal` | `pm_task.due_date + status` 聚合 | 逾期任务数，由 Java 计算 |
| `taskBlockedTotal` | `pm_task` 阻塞属性或开放风险聚合 | 阻塞任务数，由 Java 计算 |
| `riskTotal` | `pm_risk` 聚合 | 风险总数，由 Java 计算 |
| `highRiskTotal` | `pm_risk.level` 聚合 | 高风险数量，由 Java 计算 |
| `dataSnapshotAt` | `pm_project_brief.data_snapshot_at` | 生成简报所用业务数据快照时间 |
| `generatedAt` | `pm_project_brief.generated_at` | 简报生成时间 |
| `modelProvider` | `agent_trace.provider` | 模型提供方 |
| `model` | `agent_trace.model` | 模型名称 |
| `traceId` | `pm_project_brief.trace_id` | 简报生成调用链标识 |

### 接口

#### `POST /api/v1/agent/jobs`

- `jobType=project_summary`；
- Java 从 `pm_project`、`pm_task`、`pm_task_status_log`、`pm_risk`、`pm_project_activity` 构建业务快照；
- Agent 只生成 `summary`、`healthStatus`、`developmentReview`、`iterationInfo`、`recommendations`、`missingData` 和 `sourceReferences`；
- Java 将结果保存到 `pm_project_brief`。

#### `GET /api/v1/agent/jobs/{jobId}`

- 返回简报作业状态和最终结构化简报；
- 项目管理页平时读取 Java 保存的最新简报，不应每次打开页面都重新调用模型。

---

## 6. 模块 3：风险候选

### 数据库表

| 表名 | 所属服务 | 作用 | 当前状态 |
|---|---|---|---|
| `pm_project` | Java | 风险所属项目 | 已存在 |
| `pm_task` | Java | 风险关联任务 | 已存在 |
| `pm_project_file` | Java | 风险证据文件 | 待新增 |
| `pm_risk` | Java | 风险候选和正式风险 | 待新增 |
| `pm_risk_event` | Java | 风险确认、处理、解决和关闭过程 | 待新增 |
| `agent_trace` | Java | 风险分析 Trace | 待新增 |

### 需要展示的数据字段

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `candidateKey` | `pm_risk.external_key` | Agent 生成的稳定候选标识 |
| `riskId` | `pm_risk.id` | Java 持久化后生成的风险 ID，持久化前为空 |
| `projectId` | `pm_risk.project_id` | 所属项目 |
| `taskId` | `pm_risk.task_id` | 关联任务，可为空 |
| `title` | `pm_risk.title` | 风险标题 |
| `description` | `pm_risk.description` | 风险说明 |
| `category` | `pm_risk.category` | 风险类别，例如依赖、安全、进度、质量 |
| `level` | `pm_risk.level` | 风险等级，例如 high/medium/low |
| `probability` | `pm_risk.probability` | 发生概率 |
| `impact` | `pm_risk.impact` | 影响程度 |
| `status` | `pm_risk.status` | `draft/confirmed/processing/resolved/closed/rejected` |
| `reason` | `pm_risk.reason` | Agent 判断为风险的主要原因 |
| `evidence[].type` | `pm_risk.evidence_json` | 证据类型，例如 file/task/activity |
| `evidence[].referenceId` | `pm_risk.evidence_json` | 证据关联记录 ID |
| `evidence[].path` | `pm_risk.evidence_json`，关联 `pm_project_file.relative_path` | 证据文件路径 |
| `evidence[].summary` | `pm_risk.evidence_json` | 脱敏后的证据摘要 |
| `suggestedAction` | `pm_risk.suggested_action` | 建议处理动作 |
| `source` | `pm_risk.source` | `manual/agent/file_analysis/task_analysis` |
| `requiresConfirmation` | `pm_risk.requires_confirmation` | 是否必须人工确认 |
| `generatedAt` | `pm_risk.generated_at` | 候选生成时间 |
| `confirmedBy` | `pm_risk_event.operator_id` | 风险确认人 |
| `confirmedAt` | `pm_risk_event.created_at` | 风险确认时间 |
| `traceId` | `pm_risk.trace_id` | 风险生成调用链标识 |

### 接口

#### `POST /api/v1/agent/jobs`

- `jobType=risk_analysis`；
- Java 提供项目、任务、逾期、阻塞、项目文件摘要和已有风险；
- Agent 返回结构化风险候选，不创建正式风险；
- Java 将候选写入 `pm_risk`，初始状态为 `draft`。

#### `GET /api/v1/agent/jobs/{jobId}`

- 返回风险分析进度和风险候选数组；
- 用户确认、处理和关闭风险均调用 Java 风险接口，不调用 Agent 作业接口。

---

## 7. 模块 4：任务拆解草稿

### 数据库表

| 表名 | 所属服务 | 作用 | 当前状态 |
|---|---|---|---|
| `pm_project` | Java | 任务所属项目 | 已存在 |
| `pm_project_file` | Java | 任务拆解的文件依据 | 待新增 |
| `pm_risk` | Java | 任务关联风险 | 待新增 |
| `pm_task_draft` | Java | Agent 生成、等待确认的任务草稿 | 待新增 |
| `pm_task` | Java | 用户确认后的正式任务 | 已存在 |
| `pm_task_status_log` | Java | 正式任务初始状态日志 | 已存在 |
| `agent_trace` | Java | 任务拆解 Trace | 待新增 |

### 需要展示的数据字段

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `draftKey` | `pm_task_draft.external_key` | Agent 生成的稳定草稿标识 |
| `draftId` | `pm_task_draft.id` | Java 持久化后的草稿 ID |
| `projectId` | `pm_task_draft.project_id` | 所属项目 |
| `title` | `pm_task_draft.title` | 任务标题 |
| `description` | `pm_task_draft.description` | 任务目标和实现说明 |
| `priority` | `pm_task_draft.priority` | 建议优先级 P0 到 P3 |
| `suggestedStatus` | `pm_task_draft.suggested_status` | 建议初始状态，正式创建时默认使用 `pending` |
| `dueDate` | `pm_task_draft.due_date` | 建议截止日期，可为空 |
| `estimatedHours` | `pm_task_draft.estimated_hours` | 建议预估工时，可为空 |
| `deliveryNode` | `pm_task_draft.delivery_node` | 交付节点，例如今天、明天、本周 |
| `acceptanceCriteria` | `pm_task_draft.acceptance_criteria_json` | 验收标准列表 |
| `dependencyHints` | `pm_task_draft.dependency_hint_json` | 依赖和前置事项列表 |
| `relatedRiskIds` | `pm_task_draft.related_risk_json`，关联 `pm_risk.id` | 关联风险 ID 列表 |
| `sourceReferences` | `pm_task_draft.source_reference_json` | 文件、风险和项目简报引用 |
| `status` | `pm_task_draft.status` | `draft/confirmed/rejected/expired` |
| `requiresConfirmation` | `pm_task_draft.requires_confirmation` | 是否需要人工确认，固定为 `true` |
| `generatedAt` | `pm_task_draft.generated_at` | 草稿生成时间 |
| `confirmedTaskId` | `pm_task_draft.confirmed_task_id`，关联 `pm_task.id` | 确认后生成的正式任务 ID |
| `traceId` | `pm_task_draft.trace_id` | 任务拆解调用链标识 |

### 接口

#### `POST /api/v1/agent/jobs`

- `jobType=task_decomposition`；
- Java 提供项目摘要、已确认风险、已有任务和项目文件摘要；
- Agent 返回任务草稿数组；
- Java 将草稿写入 `pm_task_draft`。

#### `GET /api/v1/agent/jobs/{jobId}`

- 返回任务拆解进度和草稿数组；
- 用户确认后由 Java 将 `pm_task_draft` 转为 `pm_task` 并写入 `pm_task_status_log`；
- Agent 不直接创建、修改或删除正式任务。

---

## 8. 模块 5：PM 助手对话与执行过程

### 数据库表

| 表名 | 所属服务 | 作用 | 当前状态 |
|---|---|---|---|
| `agent_conversation_message` | Java | 当前一轮用户与助手消息、模型和 Token 用量 | 已存在 |
| `agent_trace` | Java | 一次 Agent 执行的完整 Trace | 待新增 |
| `agent_tool_call` | Java | Agent 工具调用记录 | 待新增 |
| `pm_project` | Java | 对话项目上下文 | 已存在 |
| `pm_task` | Java | 对话任务上下文 | 已存在 |
| `pm_risk` | Java | 对话风险上下文 | 待新增 |

### 需要展示的数据字段

| 字段 | 所属表 | 表示内容 |
|---|---|---|
| `conversationId` | `agent_conversation_message.conversation_id` | 会话 ID |
| `conversationSegmentId` | `agent_conversation_message.iteration_id` | 对话分段 ID；后续应重命名，避免与业务迭代混淆 |
| `turnIndex` | `agent_conversation_message.turn_index` | 会话轮次序号 |
| `projectId` | `agent_conversation_message.project_id` | 当前项目上下文 |
| `taskId` | `agent_conversation_message.task_id` | 当前任务上下文，可为空 |
| `userContent` | `agent_conversation_message.user_content` | 用户本轮输入 |
| `answer` | `agent_conversation_message.assistant_content` | Agent 最终回答 |
| `modelProvider` | `agent_trace.provider` | 模型提供方 |
| `model` | `agent_conversation_message.model` | 模型名称 |
| `toolCalls[].toolCallId` | `agent_tool_call.id` | 工具调用 ID |
| `toolCalls[].toolName` | `agent_tool_call.tool_name` | 工具名称 |
| `toolCalls[].status` | `agent_tool_call.status` | 工具调用状态 |
| `toolCalls[].displaySummary` | `agent_tool_call.output_summary` | 面向用户的脱敏工具结果摘要 |
| `toolCalls[].costMs` | `agent_tool_call.cost_ms` | 工具执行耗时 |
| `toolCalls[].errorMessage` | `agent_tool_call.error_message` | 工具失败中文说明 |
| `referencedData` | `agent_trace.reference_json` | 回答引用的项目、任务、风险和文件标识 |
| `requiresConfirmation` | `agent_trace.requires_confirmation` | 是否包含待确认写动作 |
| `inputTokens` | `agent_conversation_message.input_tokens` | 本轮输入 Token 数 |
| `outputTokens` | `agent_conversation_message.output_tokens` | 本轮输出 Token 数 |
| `totalTokens` | `agent_conversation_message.total_tokens` | 本轮总 Token 数 |
| `status` | `agent_conversation_message.status` | 本轮调用状态 |
| `errorMessage` | `agent_conversation_message.error_message` | 失败原因 |
| `createdAt` | `agent_conversation_message.created_at` | 消息生成时间 |
| `traceId` | `agent_conversation_message.trace_id` | 对话调用链标识 |

### 接口

#### `POST /api/v1/agent/chat`

- 绑定 `agent_conversation_message`、`agent_trace`、`agent_tool_call`；
- `stream=false` 时返回完整 JSON；
- `stream=true` 时返回 SSE 事件；
- Java 负责提供会话历史和业务上下文，并持久化最终结果；
- Agent 通过 Java 只读工具获取项目、任务和风险事实数据。

SSE 最少包含以下事件：

| 事件 | 展示内容 | 持久化绑定 |
|---|---|---|
| `meta` | 会话、用户、模型和 Trace 元数据 | `agent_trace` |
| `tool_call` | 正在调用的工具 | `agent_tool_call` |
| `tool_result` | 工具执行状态和摘要 | `agent_tool_call` |
| `token` | 流式回答文本 | 最终合并到 `agent_conversation_message.assistant_content` |
| `error` | 中文错误信息 | `agent_trace.error_message`、`agent_conversation_message.error_message` |
| `done` | 模型、Token 和结束状态 | `agent_trace`、`agent_conversation_message` |

---

## 9. 不应由 Agent 服务返回的页面数据

以下数据应由 Java 直接查询或聚合，不能由模型计算或编造：

| 页面数据 | 数据来源 |
|---|---|
| 当前用户、用户名、头像 | `pm_user` |
| 项目总数、进行中项目数 | `pm_project` 聚合 |
| 项目名称、状态、周期、星标 | `pm_project` |
| 任务总数、完成数、状态分布 | `pm_task` 聚合 |
| 今日待办、延期任务 | `pm_task.due_date + status` 聚合 |
| 任务负责人、优先级、截止日期 | `pm_task`、`pm_user` |
| 阻塞任务 | `pm_task` 阻塞属性或未关闭风险聚合 |
| 风险数量、风险状态 | `pm_risk` 聚合 |
| 风险处理历史 | `pm_risk_event` |
| 近期动态 | `pm_project_activity`、任务状态日志、风险事件 |
| 项目文件数量和存储状态 | `pm_project_file` |

Agent 可以解释这些数据、总结趋势和生成建议，但不能作为这些字段的唯一事实源。

## 10. 接口与表字段绑定总览

| 接口 | 作业类型 | 输入表 | 输出表 | 主要结果字段 |
|---|---|---|---|---|
| `POST /api/v1/agent/jobs` | `project_initialization` | `pm_project`、`pm_project_source`、`pm_project_file` | `pm_project_analysis_job`、`agent_trace` | 进度、文件统计、技术栈、模块边界 |
| `POST /api/v1/agent/jobs` | `project_summary` | `pm_project`、`pm_task`、`pm_task_status_log`、`pm_risk`、`pm_project_activity` | `pm_project_brief`、`agent_trace` | 回顾、阶段信息、建议、缺失数据 |
| `POST /api/v1/agent/jobs` | `risk_analysis` | `pm_project`、`pm_task`、`pm_project_file`、已有 `pm_risk` | `pm_risk` 草稿、`agent_trace` | 风险候选、证据、建议动作 |
| `POST /api/v1/agent/jobs` | `task_decomposition` | `pm_project`、`pm_project_file`、`pm_risk`、已有 `pm_task` | `pm_task_draft`、`agent_trace` | 任务草稿、优先级、验收标准、依赖 |
| `GET /api/v1/agent/jobs/{jobId}` | 全部作业类型 | `pm_project_analysis_job`、`agent_trace` | 无新增写入 | 作业进度、错误和最终结果 |
| `POST /api/v1/agent/chat` | 对话 | 会话历史、Java 工具返回的业务快照 | `agent_conversation_message`、`agent_trace`、`agent_tool_call` | 回答、工具过程、引用、Token、Trace |

## 11. 最小请求结构

### 11.1 创建 Agent 作业

```json
{
  "jobType": "project_initialization",
  "projectId": 1,
  "sourceVersionId": 3,
  "contextSnapshot": {},
  "options": {
    "generateBrief": true,
    "generateRiskCandidates": true
  }
}
```

请求头必须包含：

```text
X-Trace-Id
X-User-Id
X-Tenant-Id
X-Idempotency-Key
```

### 11.2 查询 Agent 作业

```json
{
  "jobId": "job_20260711_001",
  "jobType": "project_initialization",
  "projectId": 1,
  "status": "running",
  "progressPercent": 62,
  "currentStage": "detect_tech_stack",
  "stages": [],
  "resultType": null,
  "result": null,
  "errorCode": null,
  "errorMessage": null,
  "traceId": "8f67d6d70a2b4af8b0c1d5480a0a0001"
}
```

## 12. 实现顺序

1. 先统一 Java 与 Python 的 `traceId`、用户、租户和会话字段类型；
2. 新增 `pm_project_analysis_job` 和 `agent_trace`，实现统一作业状态；
3. 由 Java 向 `project_initialization` 作业提供受控文件元数据和文件引用；
4. 实现项目简报结构化输出并保存到 `pm_project_brief`；
5. 实现风险候选并保存到 `pm_risk` 草稿；
6. 实现任务拆解并保存到 `pm_task_draft`；
7. 完善 `/api/v1/agent/chat` 的流式、工具调用和失败 Trace；
8. 由 Java 提供面向前端的工作台、项目概览、风险和任务看板聚合接口。

## 13. 风险与取舍

1. Python 不接收服务器本地 `root_path`，项目文件必须通过 Java 受控接口或事件进入解析链路；
2. 作业结果中的大文件列表和证据内容不能全部写入 `result_json`，应保存引用和脱敏摘要；
3. 项目初始化属于长任务，不能在 Java 数据库事务中等待 Agent 完成；
4. Agent 生成的风险候选和任务草稿必须经过人工确认；
5. 页面打开时应读取 Java 已持久化结果，不应为每次页面刷新重复调用模型；
6. 当前没有必要引入 RabbitMQ、Celery、Redis 或向量数据库，可先使用数据库作业表和受控进程内执行器完成 MVP。

## 14. 验收标准

- Java 可以使用统一作业接口发起四类 Agent 能力；
- 初始化页面可以显示真实进度、阶段、成功和失败状态；
- 项目管理页可以读取已落库的进度简报；
- 风险分析只生成候选，未经确认不会成为已确认风险；
- 任务拆解只生成草稿，未经确认不会写入正式任务；
- 所有 Agent 结果都能追溯到 `traceId`、模型和 Token 用量；
- 项目、任务和风险统计均由 Java 业务数据计算；
- 前端不直接访问 `agent-service`；
- `agent-service` 不直接访问 Java 业务数据库。

## 15. 待确认问题

1. 正式项目资料入口采用浏览器文件集、ZIP、Git 仓库还是桌面采集器；
2. `pm_project_analysis_job` 的执行状态由 Java 主导还是 Agent 进程主导；
3. 项目简报是否需要保留全部历史版本，还是只保留最近若干版本；
4. 风险证据是否允许保存短代码片段，还是只保存文件路径和脱敏摘要。
