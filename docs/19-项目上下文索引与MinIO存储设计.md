# 项目上下文索引与 MinIO 存储设计

## 1. 对象布局

```text
PM-AGENT/{userId}/{projectId}/
├── project/{storageName}
├── user/{storageName}
└── system/
    ├── index.json
    ├── project_specification.json  # 初始化与旧版迁移来源
    ├── file_details/{storageUuid}-{contentHash}-{pathHash}.json
    └── context/
        ├── manifest.json
        ├── versions/{revision}/
        ├── drafts/{draftId}/
        ├── edits/
        └── migration/
```

文件对象键由 Python `StorageLocationFactory` 生成，上下文对象键由 `ContextStore` 按所属范围生成。公开 API 不接受任意 `system` 对象键。个人通用习惯和词条使用独立的 `PM-AGENT/user_context/{userId}/context/` 范围。

## 2. 权威数据

- MySQL `pm_project_file` 是文件状态、路径与分析投影的权威源。
- 原始文件和完整详情对象保存在 MinIO。
- `system/index.json` 是可重建快照，不是业务事实源。
- 重建索引时不下载旧文件做读改写，而是从数据库完整生成。
- 创建项目时先写入合法空项目规范，再写入空索引；后续解析批次同样先刷新项目规范，最后发布索引。
- 已学习的习惯、词条、短长期记忆及项目规则以 MinIO `context/manifest.json` 引用的分类文件为唯一有效内容源；草稿未确认前不参与召回。MySQL 旧正文表仅用于迁移和历史核对。
- 文件解析生成的项目规范与人工确认内容共用项目清单；新规范原始聚合文档由清单的 `specification` 引用读取。旧固定 `project_specification.json` 不再代表迁移后的当前版本。
- 发布先写不可变版本，再以 ETag 条件更新清单；缓存仅保存后端有限内存中的不可变正文，清单每次重新读取。详见 [云端上下文与显式学习改造](./27-云端上下文与显式学习改造.md)。

## 3. 索引模块边界

`index.json` 的代码归属于 `app/project_context/index/`：

```text
index/
├── __init__.py
├── schemas.py
└── service.py
```

- `schemas.py` 以 `ProjectIndexDocument` 及其嵌套 Pydantic 模型描述完整快照，覆盖存储信息、统计信息、文件条目、上传失败条目和系统引用。
- `service.py` 中的 `ProjectIndexService` 只负责强类型快照构建、空快照初始化和 MinIO 发布。它接收业务 Service 已查询出的项目与文件数据，不持有 Session，不调用 Repository，也不自行查询数据库。
- 项目初始化、文件管理和文件解析 Service 负责数据库查询、事务边界及发布编排；项目规范和项目索引模块之间不直接调用。
- `write()` 将强类型模型转换为 JSON 后写入 `system/index.json`。索引协议版本为 `2.0.0`，文件条目不再暴露分析管线版本。

## 4. 文件详情

`detail_ref` 形如：

```text
system/file_details/a1b2c3d4e5f67890-{contentHash}-{pathHash}.json
```

文件详情的项目 ID、文件 ID、存储标识、路径、大小、内容类型、内容哈希和时间由服务端构造。模型只返回模块、类型、语言、重要度、摘要、关键词、内容切片、风险和结构化规则候选等语义字段，避免模型控制文件身份。

详情对象键包含稳定存储标识、完整内容哈希和路径哈希。分析结果先写快照对象，再以文件 ID、项目 ID、内容哈希和乐观锁版本条件更新数据库引用；内容或路径在分析期间变化时，旧结果只能留下未引用对象，不能覆盖当前详情。文件变化解除数据库引用后，业务服务尽力清理旧详情对象。

规则候选保存在对应详情对象中，不创建本地临时规则文件。项目规范刷新时读取当前有效详情的规则候选，并由服务端补充稳定的 `file_id`、`content_hash` 和 `detail_ref` 来源引用。

## 5. 事务边界

- 查询候选文件后结束数据库事务，再从 MinIO 读取和调用 LLM。
- 详情写入 MinIO 后，以文件 ID、项目 ID、内容哈希和乐观锁版本条件更新投影。
- 条件更新失败表示文件内容或路径已变化，当前分析结果不得覆盖新快照。
- 单文件分析前执行敏感内容检查；明确的私钥或凭据内容不得进入模型 Prompt，常见密钥和连接串先脱敏再分析。
- 最后结束数据库读取事务，先刷新项目规范，再写完整索引；`index.json` 始终从 MySQL 全量生成，不读取旧索引做增量修改。
