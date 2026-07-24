# 项目上下文索引与 MinIO 存储设计

## 1. 对象布局

```text
PM-AGENT/{userId}/{projectId}/
├── project/{storageName}
├── user/{storageName}
└── system/
    ├── index.json
    └── file_details/{detailName}.json
```

对象键只由 Python `StorageLocationFactory` 生成。公开 API 不接受 `system` 对象键。

## 2. 权威数据

- MySQL `pm_project_file` 是文件状态、路径与分析投影的权威源。
- 原始文件和完整详情对象保存在 MinIO。
- `system/index.json` 是可重建快照，不是业务事实源。
- 重建索引时不下载旧文件做读改写，而是从数据库完整生成。

## 3. 文件详情

`detail_ref` 形如：

```text
system/file_details/README-a1b2c3d4e5f67890.json
```

模型输出必须与请求中的项目 ID、文件 ID、存储标识、路径、大小、内容类型、内容哈希和分析版本一致，才能写入详情与数据库投影。

## 4. 事务边界

- 查询候选文件后结束数据库事务，再从 MinIO 读取和调用 LLM。
- 详情写入 MinIO 后，以文件 ID、项目 ID 和内容哈希条件更新投影。
- 条件更新失败表示文件已变化，当前分析结果不得覆盖新版本。
- 最后结束数据库读取事务，再写完整索引。
