# 项目上下文 JSON 文件规范

## 1. 背景

PM-Agent 的项目上下文索引与记忆系统需要在用户选择本地项目目录后，持续维护项目文件、项目规范、项目记忆、用户习惯和增量更新记录。

本文件用于固定系统内部 JSON / JSONL 文件的结构，作为后续实现扫描、召回、记忆演进、`project.md` 内化和调试审计的格式依据。

## 2. 目标

1. 固定各类 JSON 文件的字段结构，减少后续实现时的格式漂移；
2. 明确每类文件的职责边界，避免索引、详情、规范和记忆互相污染；
3. 支持 `index.json → file_details → 原始文件 / 记忆` 的轻量召回链路；
4. 支持文件增量扫描、内容 hash 对比、软删除和更新日志记录；
5. 为后续 BM25、向量检索、AST 解析和更完整 RAG 预留结构。

## 3. 总体结构

本文中的路径分为两层：

- 逻辑路径：用于 JSON 文件内部引用、检索路由和人工排查，可以保留目录层级；
- 云端对象路径：用于后续对象存储上传、下载、覆盖和删除，采用业务分区后的稳定分层结构。

### 3.1 逻辑路径结构

```text
.pm-agent/projects/<project_id>/
  index.json
  file_details/
    backend/
    frontend/
    agent-service/
    _archive/
  project_specification.json
  long_term_memory.json
  short_term_memory.json
  user_habits/
    work.json
    life.json
    thinking.json
    specification.json
    tooling.json
  update_journal.jsonl
```

### 3.2 云端对象路径结构

当前 MinIO 上传能力仍属于文件上传初始化实验。后续完善项目上下文 JSON 存储时，不应继续沿用普通上传文件的 `uuid8-文件名` 扁平路径，而应使用稳定对象路径。

对象存储桶由 `MINIO_BUCKET` 配置，默认值为：

```text
pm-agent
```

项目上下文 JSON 文件统一放入 `project` 业务分区：

```text
business = project
```

推荐云端对象根路径为：

```text
PM-AGENT/<user_id>/<project_id>/project/context/
```

因此，任意项目上下文 JSON 的云端对象名为：

```text
PM-AGENT/<user_id>/<project_id>/project/context/<logical_path>
```

对外返回路径为：

```text
<MINIO_PUBLIC_BASE_URL>/PM-AGENT/<user_id>/<project_id>/project/context/<logical_path>
```

后续代码需要支持安全相对路径校验：允许 `/` 表示对象名前缀，但必须禁止 `..`、`\`、空路径、绝对路径和非法字符。

### 3.3 逻辑路径与云端对象路径映射

| 逻辑路径 | 云端对象路径 |
|---|---|
| `index.json` | `PM-AGENT/<user_id>/<project_id>/project/context/index.json` |
| `file_details/backend/auth/file-backend-auth-controller.json` | `PM-AGENT/<user_id>/<project_id>/project/context/file_details/backend/auth/file-backend-auth-controller.json` |
| `project_specification.json` | `PM-AGENT/<user_id>/<project_id>/project/context/project_specification.json` |
| `long_term_memory.json` | `PM-AGENT/<user_id>/<project_id>/project/context/long_term_memory.json` |
| `short_term_memory.json` | `PM-AGENT/<user_id>/<project_id>/project/context/short_term_memory.json` |
| `user_habits/work.json` | `PM-AGENT/<user_id>/<project_id>/project/context/user_habits/work.json` |
| `user_habits/thinking.json` | `PM-AGENT/<user_id>/<project_id>/project/context/user_habits/thinking.json` |
| `user_habits/specification.json` | `PM-AGENT/<user_id>/<project_id>/project/context/user_habits/specification.json` |
| `user_habits/tooling.json` | `PM-AGENT/<user_id>/<project_id>/project/context/user_habits/tooling.json` |
| `user_habits/life.json` | `PM-AGENT/<user_id>/<project_id>/project/context/user_habits/life.json` |
| `update_journal.jsonl` | `PM-AGENT/<user_id>/<project_id>/project/context/update_journal.jsonl` |

例如：

```text
逻辑路径：
file_details/backend/auth/file-backend-auth-controller.json

云端 object_name：
PM-AGENT/u001/local-pm-agent-001/project/context/file_details/backend/auth/file-backend-auth-controller.json
```

### 3.4 路径使用规则

```text
JSON 内部引用优先使用逻辑路径。
MinIO 上传、下载、覆盖和删除使用 url_path / object_name。
云端对象路径由 object_prefix + logical_path 组成。
LLM 不直接拼接 user_id、project_id 或云端完整对象路径。
file_details 逻辑路径和云端对象路径都保留目录层级。
```

当前代码中的 `TreeIndexWriter` 会将文件树扫描结果写为 `Project_Index.json`。该文件属于现有文件树扫描产物；本文中的 `index.json` 是项目上下文总索引规范文件，后续实现时应避免两者命名职责混淆。

| 文件 | 格式 | 职责 |
|---|---|---|
| `index.json` | JSON | 总索引，只做快速命中和路由 |
| `file_details/*.json` | JSON | 单文件详情、职责摘要和可召回切片 |
| `project_specification.json` | JSON | 项目规范、阶段目标、技术约束和风险边界 |
| `long_term_memory.json` | JSON | 长期稳定决策、阶段演进和关键结论 |
| `short_term_memory.json` | JSON | 当前任务窗口内的临时上下文 |
| `user_habits/*.json` | JSON | 用户稳定协作偏好，按类别拆分 |
| `update_journal.jsonl` | JSONL | 增量更新日志，用于审计和调试 |

## 4. 通用约定

### 4.1 schema_version

所有 JSON 文件必须包含 `schema_version`，用于后续格式升级和兼容判断。

```json
{
  "schema_version": "1.0.0"
}
```

### 4.2 稳定 ID

所有可被更新、覆盖、引用的对象必须具备稳定 `id`。

```text
文件移动时保留 id。
内容变化时保留 id。
删除文件时保留 id 并标记 status=deleted。
LLM 输出变更时必须带目标 id，由程序按 id 合并。
```

### 4.3 覆盖规则

禁止用 LLM 输出整文件覆盖旧 JSON。必须采用：

```text
读取旧 JSON
→ 生成 changes 或目标条目
→ 程序按 id 合并
→ 未命中的旧条目原样保留
→ 冲突条目标记 conflicted / evolved / pending_review
```

## 5. index.json

### 5.1 职责

`index.json` 是所有内部上下文文件的总入口，负责第一跳快速检索和路由。

它只回答一个问题：

```text
用户问题或系统任务应该优先读取哪些详情文件、记忆文件或原始文件？
```

### 5.2 不允许存放

- 原始文件全文；
- 大段代码；
- 大段文档；
- Prompt 内容；
- 内部评分细节；
- 用户敏感信息；
- `file_details` 中完整的 `content_slices`。

### 5.3 结构

```json
{
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "generated_at": "2026-07-02T00:00:00",
  "storage": {
    "provider": "minio",
    "bucket": "pm-agent",
    "business": "project",
    "object_prefix": "PM-AGENT/u001/local-pm-agent-001/project/context/",
    "logical_root": "context/"
  },
  "summary": {
    "total_nodes": 1200,
    "active_files": 430,
    "ignored_files": 700,
    "deleted_files": 3,
    "detail_files": 180
  },
  "entries": [
    {
      "id": "file-backend-auth-controller",
      "path": "backend/src/main/java/com/ning/pm/auth/controller/AuthController.java",
      "module": "backend-auth",
      "kind": "backend_code",
      "language": "java",
      "status": "active",
      "importance": "high",
      "quick_fingerprint": "qf:sha256:9f2c1a7b8e4d6a0c",
      "content_hash": "sha256:xxx",
      "summary": "认证接口控制器",
      "keywords": ["认证", "登录", "注册", "Sa-Token"],
      "detail_ref": "file_details/backend/auth/file-backend-auth-controller.json",
      "updated_at": "2026-07-02T00:00:00"
    }
  ],
  "refs": {
    "file_details": "file_details/",
    "project_specification": "project_specification.json",
    "long_term_memory": "long_term_memory.json",
    "short_term_memory": "short_term_memory.json",
    "user_habits": "user_habits/",
    "update_journal": "update_journal.jsonl"
  }
}
```

### 5.4 字段说明

| 字段 | 说明 |
|---|---|
| `summary.total_nodes` | 扫描后识别到的总节点数量 |
| `summary.active_files` | 当前有效文件数量 |
| `summary.ignored_files` | 被 ignore 规则跳过的文件数量 |
| `summary.deleted_files` | 软删除文件数量 |
| `summary.detail_files` | 已生成详情文件的数量 |
| `storage.provider` | 云端存储提供方，当前预留为 `minio` |
| `storage.bucket` | 对象存储桶，默认 `pm-agent` |
| `storage.business` | 云端业务分区，项目上下文 JSON 使用 `project` |
| `storage.object_prefix` | 云端对象根路径，用于拼接逻辑路径 |
| `storage.logical_root` | 逻辑根目录标识，默认 `context/` |
| `entries[].id` | 稳定文件 ID，必须与 `file_details.id` 对齐 |
| `entries[].path` | 当前源文件相对路径 |
| `entries[].module` | 粗粒度业务模块 |
| `entries[].kind` | 粗粒度文件类型，如 `backend_code`、`frontend_code`、`agent_code`、`doc`、`config` |
| `entries[].quick_fingerprint` | 已计算后的快速指纹，用于快速判断文件是否可能变化 |
| `entries[].content_hash` | 文件内容 hash，用于精确判断内容是否变化 |
| `entries[].detail_ref` | 对应 `file_details` 文件路径 |

### 5.5 协作关系

```text
用户问题 / 系统任务
→ 读取 index.json
→ 按 module、kind、keywords、status 命中候选 entry
→ 通过 detail_ref 读取 file_details
→ 必要时读取原始文件 source_range
```

## 6. update_journal.jsonl

### 6.1 职责

`update_journal.jsonl` 记录每次上下文系统更新动作，用于调试、审计和后续回滚参考。

它采用 JSONL 格式，一行一个事件，不使用数组包裹。

### 6.2 结构

```jsonl
{"event_id":"evt-001","project_id":"local-pm-agent-001","event_type":"file_modified","target":"file_details/backend/auth/file-backend-auth-controller.json","source":"backend/src/main/java/com/ning/pm/auth/controller/AuthController.java","summary":"文件内容 hash 变化，已更新对应 index entry 和 file detail。","created_at":"2026-07-02T00:00:00"}
{"event_id":"evt-002","project_id":"local-pm-agent-001","event_type":"file_deleted","target":"file_details/backend/auth/file-backend-auth-controller.json","source":"backend/src/main/java/com/ning/pm/auth/controller/AuthController.java","summary":"源文件已删除，对应 index entry 和 file detail 已标记为 deleted。","created_at":"2026-07-02T00:00:00"}
{"event_id":"evt-003","project_id":"local-pm-agent-001","event_type":"memory_promoted","target":"long_term_memory.json","source":"short_term_memory.json#task-freeze-json-format-spec","summary":"短期记忆确认具备长期价值，已生成长期记忆候选。","created_at":"2026-07-02T00:00:00"}
{"event_id":"evt-004","project_id":"local-pm-agent-001","event_type":"project_md_internalized","target":"project_specification.json","source":"project.md#用户可编辑区","summary":"用户可编辑区中的项目规则补充已内化为项目规范候选。","created_at":"2026-07-02T00:00:00"}
```

### 6.3 记录范围

| 动作 | `event_type` 示例 | 是否记录 |
|---|---|---:|
| 文件新增 | `file_added` | 是 |
| 文件修改 | `file_modified` | 是 |
| 文件删除 | `file_deleted` | 是 |
| 文件移动 | `file_moved` | 是 |
| 短期记忆晋升 | `memory_promoted` | 是 |
| 长期记忆演化 | `memory_evolved` | 是 |
| 用户习惯更新 | `user_habit_updated` | 是 |
| `project.md` 内化 | `project_md_internalized` | 是 |

## 7. user_habits/*.json

### 7.1 职责

`user_habits/*.json` 保存用户稳定协作偏好，按类别拆分，避免单个习惯文件膨胀。

### 7.2 分类文件

```text
user_habits/
  work.json
  life.json
  thinking.json
  specification.json
  tooling.json
```

### 7.3 结构

```json
{
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "category": "work",
  "updated_at": "2026-07-02T00:00:00",
  "user_habits": [
    {
      "id": "work-structured-design-first",
      "title": "先固定结构再进入实现",
      "habit": "用户在复杂功能开发前倾向先讨论并固定结构方案，再进入具体实现。",
      "scope": "project_collaboration",
      "status": "active",
      "confidence": "high",
      "importance": "high",
      "tags": ["结构设计", "开发顺序", "方案收束", "协作方式"],
      "signals": [
        "先给出结构",
        "先固定格式",
        "收束到文档",
        "暂且无需额外说明"
      ],
      "source_type": "conversation",
      "source_refs": [
        {
          "type": "conversation",
          "summary": "用户多次要求先输出 JSON 格式，再将确认后的版本收束到规范文档。"
        }
      ],
      "applicable_scenarios": [
        "设计复杂 JSON 结构",
        "设计 Agent 上下文系统",
        "编写技术规范文档",
        "进入代码实现前的方案确认"
      ],
      "avoid_when": [
        "用户明确要求直接实现",
        "任务是简单文件创建或查询"
      ],
      "change_type": "created",
      "previous_versions": [],
      "created_at": "2026-07-02T00:00:00",
      "updated_at": "2026-07-02T00:00:00"
    }
  ],
  "changes": [
    {
      "change_id": "chg-001",
      "change_type": "created",
      "target_id": "work-structured-design-first",
      "summary": "记录用户偏好先固定结构方案再进入实现。",
      "created_at": "2026-07-02T00:00:00"
    }
  ],
  "ignored_items": []
}
```

### 7.4 分类说明

```text
work.json：协作方式、任务推进方式、开发节奏。
thinking.json：决策偏好、风险偏好、判断方式。
specification.json：输出格式、语言、注释、文档风格。
tooling.json：工具、模型、技术栈、命令偏好。
life.json：生活类偏好，项目 Agent 默认不主动读取。
```

## 8. long_term_memory.json

### 8.1 职责

`long_term_memory.json` 保存长期有效的项目决策、阶段演进和关键结论。

它不记录临时调试过程，不记录当前任务待办，也不记录可从代码直接读取的结构快照。

### 8.2 结构

```json
{
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "updated_at": "2026-07-02T00:00:00",
  "long_term_memory": [
    {
      "id": "decision-project-context-light-index",
      "category": "decision",
      "title": "项目上下文第一版采用轻量索引方案",
      "memory": "项目上下文第一版采用 index.json、file_details、项目规范和结构化记忆文件组合，不提前引入完整向量数据库或复杂 RAG。",
      "scope": "agent-service",
      "status": "active",
      "confidence": "high",
      "importance": "high",
      "tags": ["项目上下文", "轻量索引", "RAG", "Agent 服务"],
      "source_refs": [
        {
          "type": "doc",
          "path": "agent-service/docs/项目上下文JSON文件规范.md",
          "section": "最终冻结结论"
        }
      ],
      "evidence": [
        {
          "source": "project_doc",
          "quote": "该结构可以支撑第一版轻量召回，也能平滑演进到后续 BM25、向量检索、AST 解析和更完整的 RAG 能力。"
        }
      ],
      "related_specs": [
        "approach-light-index-first",
        "constraint-no-full-rag-v1"
      ],
      "related_files": [
        {
          "path": "agent-service/docs/项目上下文JSON文件规范.md",
          "relation": "format_specification"
        }
      ],
      "previous_versions": [],
      "created_at": "2026-07-02T00:00:00",
      "updated_at": "2026-07-02T00:00:00"
    }
  ],
  "changes": [
    {
      "change_id": "chg-001",
      "change_type": "created",
      "target_id": "decision-project-context-light-index",
      "summary": "记录项目上下文第一版采用轻量索引方案的长期决策。",
      "created_at": "2026-07-02T00:00:00"
    }
  ],
  "ignored_items": []
}
```

### 8.3 写入规则

| 内容 | 是否进入长期记忆 |
|---|---:|
| 已确认架构决策 | 是 |
| 阶段性里程碑 | 是 |
| 已验证的重要测试结论 | 是 |
| 需求范围重大变化 | 是 |
| 临时调试过程 | 否 |
| 当前任务待办 | 否 |
| 用户个人习惯 | 否 |

## 9. short_term_memory.json

### 9.1 职责

`short_term_memory.json` 保存当前任务窗口内仍有价值但尚未稳定沉淀的信息。

每条短期记忆必须具备生命周期字段：`ttl_hint`、`next_check`、`promote_candidate`、`status`。

### 9.2 结构

```json
{
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "updated_at": "2026-07-02T00:00:00",
  "short_term_memory": [
    {
      "id": "task-freeze-json-format-spec",
      "category": "task",
      "title": "固定项目上下文 JSON 文件规范",
      "memory": "当前正在逐步固定项目上下文索引与记忆系统的 JSON 文件格式，已完成 index.json、file_details、project_specification 和 long_term_memory 的结构收束。",
      "scope": "agent-service",
      "status": "active",
      "confidence": "high",
      "importance": "medium",
      "ttl_hint": "本轮 JSON 规范文档完成后复查",
      "next_check": "确认是否继续固定 user_habits、project_meta 和 update_journal 的结构。",
      "promote_candidate": true,
      "tags": ["JSON 规范", "短期任务", "项目上下文"],
      "source_refs": [
        {
          "type": "conversation",
          "summary": "用户要求逐步固定项目上下文相关 JSON 文件格式。"
        }
      ],
      "related_files": [
        {
          "path": "agent-service/docs/项目上下文JSON文件规范.md",
          "relation": "format_specification"
        }
      ],
      "created_at": "2026-07-02T00:00:00",
      "updated_at": "2026-07-02T00:00:00"
    }
  ],
  "promotion_candidates": [
    {
      "source_memory_id": "task-freeze-json-format-spec",
      "target_type": "long_term_memory",
      "reason": "如果 JSON 文件规范最终确认并用于实现，可晋升为长期项目决策。",
      "status": "pending_review"
    }
  ],
  "changes": [
    {
      "change_id": "chg-001",
      "change_type": "created",
      "target_id": "task-freeze-json-format-spec",
      "summary": "记录当前 JSON 文件规范收束任务。",
      "created_at": "2026-07-02T00:00:00"
    }
  ],
  "ignored_items": []
}
```

### 9.3 生命周期

```text
活跃短期记忆
→ 任务完成
→ 判断是否有长期价值
→ 有价值：生成长期记忆候选
→ 无价值：过期或压缩
→ 更新 short_term_memory.json
```

## 10. file_details/*.json

### 10.1 职责

`file_details/*.json` 记录单个高价值文件的职责、切片、实体、风险和相关文件。

它只描述一个源文件，不写项目规范、不写用户习惯、不写长期记忆。

### 10.2 目录划分

```text
file_details/
  backend/
    auth/
      file-backend-auth-controller.json
      file-backend-auth-service.json
    project/
      file-backend-project-service.json
  frontend/
    auth/
      file-frontend-login-page.json
  agent-service/
    project-context/
      file-agent-project-context-scanner.json
  _archive/
    deleted/
    stale/
```

### 10.3 结构

```json
{
  "id": "file-backend-auth-controller",
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "original_path": "backend/src/main/java/com/ning/pm/auth/controller/AuthController.java",
  "module": "backend-auth",
  "file_type": "code.backend.java",
  "language": "java",
  "status": "active",
  "importance": "high",
  "content_hash": "sha256:xxx",
  "role": "提供认证相关 HTTP 接口入口，负责登录、注册和当前用户查询。",
  "content_slices": [
    {
      "slice_id": "api-login",
      "type": "api",
      "summary": "登录接口接收账号密码并调用认证服务完成登录。",
      "keywords": ["登录", "认证", "Sa-Token"],
      "entities": ["/api/v1/auth/login", "AuthService", "LoginRequest"],
      "source_range": {
        "start_line": 20,
        "end_line": 45
      }
    }
  ],
  "related_topics": ["auth", "login", "backend-api"],
  "related_files": [
    {
      "path": "backend/src/main/java/com/ning/pm/auth/service/AuthService.java",
      "relation": "service_dependency"
    }
  ],
  "risk_flags": [],
  "sensitive_flags": [],
  "evidence": [
    {
      "source": "file_content",
      "quote": "认证控制器相关摘要"
    }
  ],
  "previous_versions": [
    {
      "content_hash": "sha256:old",
      "role": "旧职责摘要",
      "changed_at": "2026-07-01T00:00:00",
      "reason": "文件内容变化后重新生成详情"
    }
  ],
  "updated_at": "2026-07-02T00:00:00"
}
```

### 10.4 生成范围

```text
所有可见文件进入 index.json entries。
高价值文件生成 file_details JSON。
file_details 按模块分目录管理。
删除或长期不活跃的详情进入 _archive。
index.json 通过 detail_ref 指向对应 file_details JSON。
```

### 10.5 与 index.json 的对应关系

| `index.json` | `file_details` | 说明 |
|---|---|---|
| `entries[].id` | `id` | 必须一致 |
| `entries[].path` | `original_path` | 文件移动后两者同步更新 |
| `entries[].content_hash` | `content_hash` | 必须一致，否则详情已过期 |
| `entries[].detail_ref` | 文件路径 | 用于读取该详情文件 |

## 11. project_specification.json

### 11.1 职责

`project_specification.json` 保存项目规范、开发阶段、技术约束、编码规则、文档规则和风险边界。

它是 Agent 执行开发、分析、生成建议前必须读取的强约束文件。

### 11.2 不允许存放

- 单次任务状态；
- 用户个人习惯；
- 可从代码直接读取的文件结构快照；
- 临时调试过程。

### 11.3 结构

```json
{
  "project_id": "local-pm-agent-001",
  "schema_version": "1.0.0",
  "updated_at": "2026-07-02T00:00:00",
  "project_specification": {
    "development_stage": {
      "current_stage": "Agent 服务项目上下文能力建设阶段",
      "stage_goal": "完成文件索引、文件详情、项目规范、记忆系统和用户可见摘要链路",
      "completed": [
        "已确定 index.json 作为轻量总索引",
        "已确定 file_details 按高价值文件分片保存"
      ],
      "next_focus": [
        "固定项目规范 JSON 结构",
        "实现增量扫描和详情更新逻辑"
      ]
    },
    "development_approach": [
      {
        "id": "approach-light-index-first",
        "rule": "第一版优先使用轻量索引和文件详情召回，不提前引入完整向量数据库或复杂 RAG。",
        "scope": "agent-service",
        "status": "active",
        "confidence": "high",
        "source_refs": [
          {
            "type": "doc",
            "path": "agent-service/docs/项目上下文JSON文件规范.md"
          }
        ],
        "created_at": "2026-07-02T00:00:00",
        "updated_at": "2026-07-02T00:00:00",
        "previous_versions": []
      }
    ],
    "technical_constraints": [
      {
        "id": "constraint-no-full-rag-v1",
        "constraint": "第一版不实现完整向量数据库 RAG，后续按需要再引入 BM25、向量检索或 AST 深度解析。",
        "scope": "agent-service",
        "status": "active",
        "confidence": "high",
        "source_refs": [
          {
            "type": "doc",
            "path": "agent-service/docs/项目上下文JSON文件规范.md"
          }
        ],
        "created_at": "2026-07-02T00:00:00",
        "updated_at": "2026-07-02T00:00:00",
        "previous_versions": []
      }
    ],
    "coding_rules": [
      {
        "id": "rule-agent-no-direct-db-write",
        "rule": "Agent 服务不直接操作业务数据库，业务变更必须通过 Java 后端工具 API 完成。",
        "scope": "agent-service",
        "status": "active",
        "confidence": "high",
        "source_refs": [
          {
            "type": "project_rule",
            "path": "AGENTS.md"
          }
        ],
        "created_at": "2026-07-02T00:00:00",
        "updated_at": "2026-07-02T00:00:00",
        "previous_versions": []
      }
    ],
    "document_rules": [
      {
        "id": "rule-docs-use-markdown",
        "rule": "项目文档统一使用 Markdown 格式。",
        "scope": "all",
        "status": "active",
        "confidence": "high",
        "source_refs": [
          {
            "type": "project_rule",
            "path": "AGENTS.md"
          }
        ],
        "created_at": "2026-07-02T00:00:00",
        "updated_at": "2026-07-02T00:00:00",
        "previous_versions": []
      }
    ],
    "risk_rules": [
      {
        "id": "risk-high-impact-action-confirmation",
        "rule": "删除、权限变更、对外通知等高风险动作必须经过用户确认，索引系统只能生成建议或候选动作。",
        "scope": "agent-service",
        "status": "active",
        "confidence": "high",
        "source_refs": [
          {
            "type": "doc",
            "path": "agent-service/docs/项目上下文JSON文件规范.md"
          }
        ],
        "created_at": "2026-07-02T00:00:00",
        "updated_at": "2026-07-02T00:00:00",
        "previous_versions": []
      }
    ]
  },
  "changes": [
    {
      "change_id": "chg-001",
      "change_type": "created",
      "target_id": "approach-light-index-first",
      "summary": "创建第一版轻量索引优先的开发方式规则。",
      "created_at": "2026-07-02T00:00:00"
    }
  ],
  "ignored_items": []
}
```

### 11.4 写入来源

| 来源 | 是否允许进入 |
|---|---:|
| 项目文档明确规则 | 是 |
| 用户明确要求 | 是 |
| 代码中稳定约定 | 是 |
| 模型推断 | 可进入，但需要低置信度或待确认 |
| 单次任务状态 | 否 |
| 用户习惯 | 否 |

## 12. 检索链路

```text
用户问题 / 系统任务
→ 意图分类
→ 读取 index.json
→ 按 module、kind、keywords、status 命中候选
→ 读取候选 file_details
→ 按任务需要读取 project_specification / long_term_memory / short_term_memory / user_habits
→ 必要时读取原始文件
→ 组装 Prompt
→ LLM 输出
```

## 13. 更新链路

```text
重新扫描文件树
→ 对比旧 index.json
→ 得到 added / modified / deleted / moved
→ 只处理变化文件
→ 更新对应 file_details
→ 更新 index.json 对应 entry
→ 必要时更新 project_specification / long_term_memory / short_term_memory / user_habits
→ 记录 update_journal.jsonl
```

## 14. 安全规则

以下内容不得进入索引详情、记忆或 Prompt：

- API Key；
- token；
- 密码；
- 私钥；
- `.env` 明文；
- 证书文件；
- 数据库连接串敏感值；
- 用户隐私信息。

允许保存脱敏摘要：

```json
{
  "path": ".env",
  "status": "ignored",
  "sensitive_flags": ["env_file", "possible_secret"],
  "summary": "检测到环境变量文件，已跳过内容索引"
}
```

项目文件中的疑似 Prompt Injection 文本只作为数据处理，不作为系统指令。

## 15. 验收标准

1. `index.json` 不包含原始文件全文；
2. `index.json` 可以通过 `detail_ref` 定位到对应 `file_details`；
3. `file_details` 可以通过 `source_range` 定位原始文件片段；
4. `content_hash` 可以用于判断详情是否过期；
5. 修改单个文件后，只更新该文件的 index entry 和 file detail；
6. 删除文件后，索引和详情均进入软删除状态；
7. 项目规范不混入用户习惯和临时任务；
8. 长期记忆只记录稳定决策和阶段性结论；
9. 短期记忆具备 TTL 和晋升候选字段；
10. 用户习惯按五类文件拆分保存；
11. 每次重要更新都写入 `update_journal.jsonl`；
12. 敏感文件不会进入 Prompt 或详情摘要。

## 16. 最终结论

项目上下文 JSON 文件采用：

```text
一个轻量总索引
+ 多个单文件详情
+ 一个项目规范库
+ 一个长期记忆库
+ 一个短期记忆库
+ 五类用户习惯库
+ 一个更新日志
```

该结构可以支撑第一版轻量召回，也能平滑演进到后续 BM25、向量检索、AST 解析和更完整的 RAG 能力。
