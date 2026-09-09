# 项目上下文索引与 MinIO 存储设计

## 1. 目标

项目上下文使用稳定、可直接检查的固定对象路径。文件解析、项目更新、显式学习、Agent 召回和报告生成必须围绕同一组文件工作，不通过版本目录或清单间接寻找当前内容。

## 2. 对象布局

```text
PM-AGENT/{userId}/{projectId}/
├── project/{storageName}
├── user/{storageName}
└── system/
    ├── index.json
    ├── project_specification.json
    ├── long_term_memory.json
    ├── short_term_memory.json
    ├── update_journal.jsonl
    ├── file_details/
    │   └── {storageUuid}-{contentHash}-{pathHash}.json
    └── user_habits/
        ├── work.json
        ├── thinking.json
        ├── specification.json
        ├── tooling.json
        └── life.json
```

文件对象键和系统对象键统一由 Python `StorageLocationFactory` 根据用户、项目和相对路径生成。公开 API 不接受任意 `system` 对象键。

正式布局中不存在以下路径：

```text
system/context/
system/context/manifest.json
system/context/versions/
PM-AGENT/user_context/{userId}/context/
```

显式学习的草稿、反馈和确认计划是工作流数据，不属于正式项目上下文目录。

## 3. 权威数据与固定文件职责

| 内容 | 权威来源 | 更新方式 |
|---|---|---|
| 项目文件状态、路径、当前详情引用 | MySQL `pm_project_file` | 数据库事务与乐观锁 |
| 原始项目文件 | MinIO `project/`、`user/` | 上传、覆盖、移动或删除流程 |
| 文件语义详情 | MinIO `system/file_details/` | 按内容和路径快照写新对象，MySQL 指向当前详情 |
| 项目规范 | MinIO `system/project_specification.json` | 读取当前内容、稳定合并后覆盖同一对象键 |
| 长期记忆 | MinIO `system/long_term_memory.json` | 用户确认或显式晋升后覆盖同一对象键 |
| 短期记忆 | MinIO `system/short_term_memory.json` | 用户确认、纠正或过期整理后覆盖同一对象键 |
| 用户习惯 | MinIO `system/user_habits/*.json` | 按分类覆盖同一对象键 |
| 更新日志 | MinIO `system/update_journal.jsonl` | 只记录已完成的上下文变更 |
| 项目索引 | MinIO `system/index.json` | 从 MySQL 当前文件快照全量重建并覆盖 |

MySQL 中的学习候选、上下文条目或变更记录用于审核、来源和恢复，不得成为 Agent 召回的平行正文来源。当前生效内容以固定 MinIO 文件为准。

## 4. 索引模块边界

`index.json` 由 `app/project_context/index/` 负责强类型构建和发布：

```text
index/
├── __init__.py
├── schemas.py
└── service.py
```

- `ProjectIndexService` 接收业务 Service 已查询出的项目和文件数据，不持有 Session，不调用 Repository。
- `index.json` 是可重建快照，不是项目文件业务事实源。
- 索引从 MySQL 当前文件记录全量生成，不读取旧索引做增量修改。
- 系统引用必须始终指向固定路径：

```text
system/index.json
system/project_specification.json
system/long_term_memory.json
system/short_term_memory.json
system/user_habits/
system/update_journal.jsonl
```

- 索引不保存 manifest、revision 或版本目录引用。

## 5. 文件详情

`detail_ref` 形如：

```text
system/file_details/a1b2c3d4e5f67890-{contentHash}-{pathHash}.json
```

文件详情的项目 ID、文件 ID、存储标识、路径、大小、内容类型、内容哈希和时间由服务端构造。模型只返回模块、类型、语言、重要度、摘要、关键词、内容切片、风险、项目事实和规则候选等语义字段。

详情对象键包含稳定存储标识、完整内容哈希和路径哈希。分析结果先写详情快照，再以文件 ID、项目 ID、内容哈希和乐观锁版本条件更新数据库引用。内容或路径在分析期间变化时，旧详情只能成为未引用对象，不能覆盖当前详情。

规则候选保存在文件详情中，不创建临时规则文件。项目规范刷新只读取当前有效详情，由服务端补充稳定的 `file_id`、`content_hash` 和 `detail_ref` 来源引用。

## 6. 固定文件更新规则

- 更新前读取当前对象及其 ETag 或内容哈希。
- 在内存中完成结构校验、来源校验、稳定 ID 合并和冲突检查。
- 使用条件写覆盖原对象键，禁止无条件覆盖并发修改。
- 相同幂等键恢复时核对目标文件是否已经包含本次稳定条目，避免重复写入。
- 缓存按对象 ETag 或内容哈希失效，不依赖清单版本。
- 固定文件写入失败时保留原有效内容，并返回明确的部分失败状态。

MinIO 对象存储没有跨文件事务。一个操作更新多个目标文件时，应按文件返回结果并只重试失败项，不能通过创建整套版本目录伪装成跨文件事务。

## 7. 解析发布顺序

项目文件解析按照以下顺序发布：

1. 查询并固定本批候选文件快照；
2. 读取原文件、调用模型并写入新的 `file_details` 对象；
3. 以内容哈希和乐观锁条件回填 MySQL 当前详情引用；
4. 结束数据库读取事务；
5. 读取并稳定合并当前 `project_specification.json`；
6. 条件覆盖同一路径的项目规范；
7. 从 MySQL 全量重建并覆盖 `index.json`；
8. 把已完成变更写入 `update_journal.jsonl`。

项目规范刷新失败时保留原规范；索引仍应准确反映文件处理结果，并通过批次响应暴露规范失败。索引发布失败时不得把整批报告为成功。

## 8. 显式学习边界

显式学习不改变本文件的目录结构。模型从用户消息中提取候选，用户确认后由后端把内容合并到以下目标之一：

- `project_specification.json`
- `short_term_memory.json`
- `long_term_memory.json`
- `user_habits/{category}.json`

未确认草稿不写入这些文件。文件解析与用户确认同时涉及项目规范时，必须保留用户确认规则，并对文件来源规则执行独立合并。详细流程见 [云端上下文与显式学习改造](./27-云端上下文与显式学习改造.md)。

## 9. 验收标准

- 新项目初始化后，`system/` 只包含本文约定的文件和目录。
- 所有系统引用都是固定相对路径。
- 解析成功后原路径的项目规范和索引得到更新。
- 显式学习确认后只更新对应固定文件。
- Agent、报告、前端和人工检查读取到同一份当前内容。
- 不产生 `context/manifest.json` 或 `context/versions/`。
- 并发写入不会静默覆盖，失败可使用原幂等操作恢复。

## 10. 待确认问题

暂无。应用级正式上下文不使用版本目录；如需历史版本，优先使用变更记录或 MinIO 桶自身的对象版本能力，不能改变业务读取路径。
