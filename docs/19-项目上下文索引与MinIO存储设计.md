# 项目上下文索引与 MinIO 存储设计

## 1. 文档定位

本文档只说明 `index.json` 与 MinIO 的存储规则。批次大小、重试轮次、职责划分、数据落库和完成闸门统一以 [18-项目文件批次上传模块设计](./18-项目文件可靠上传模块设计.md) 为准。

当前固定入口为 `POST /api/v1/projects/{projectId}/file-ingest-batches/concurrent-uploads`，接收 `manifest`、`batch`、`files`。前端同一轮逐批顺序调用，每批最多 50 个文件且原始文件总大小不超过 240 MB，以适配后端 256 MB 请求上限；Java 只在当前单批内部多线程写 MinIO。

当前状态：**设计、V12 迁移和同步索引重建实现已落地**。

## 2. 核心原则

1. MySQL 是项目文件、上传状态和索引内容的唯一准确数据源。
2. MinIO 保存文件内容和可重建索引，不作为上传进度判断依据。
3. 项目创建后必须先成功写入初始 `system/index.json`，才允许上传项目文件。
4. 文件首次落库时不保存存储名、对象键、MinIO 路径和详情引用。
5. MinIO 上传成功后才把存储字段写回 MySQL。
6. MinIO 冗余对象允许暂时存在，后续按 MySQL 有效对象集合清理。
7. 前两轮存在上传失败时不重建索引。
8. 文件全部成功，或第三轮结束后，才同步完整重建一次索引。
9. 当前索引重建不使用 RabbitMQ 或 Outbox。

## 3. 存储层级

~~~text
Bucket: pm-agent

PM-AGENT/{ownerUserId}/{projectId}/
├── project/
│   └── {storageName}
├── user/
│   └── {storageName}
└── system/
    ├── index.json
    └── file_details/
~~~

规则：

- Bucket 固定为 `pm-agent`；
- 项目根前缀固定为 `PM-AGENT/{ownerUserId}/{projectId}/`；
- 普通文件业务类型只使用 `project` 和 `user`；
- `system` 只允许 Java 内部组件写入；
- 对象路径必须由 Java 统一工厂构造，不接受前端直接提供对象键；
- 预签名 URL 不持久化。

## 4. 项目初始化索引

### 4.1 前提

项目创建和初始索引上传是一个同步业务过程：

~~~mermaid
sequenceDiagram
    participant F as 前端
    participant J as Java
    participant DB as MySQL
    participant M as MinIO

    F->>J: 创建项目
    J->>DB: 插入项目，status=initializing
    J->>J: 构造空 index.json
    J->>M: PUT system/index.json
    alt 上传成功
        J->>DB: status=active
        J-->>F: 创建成功
    else 上传失败
        J->>DB: 保持不可上传状态
        J-->>F: 返回初始化失败
    end
~~~

批次上传接口必须校验项目状态为 `active`。重新处理初始化失败项目时，也必须再次确认固定位置的索引上传成功，不能直接修改状态。

### 4.2 初始结构

~~~json
{
  "project_id": 10,
  "project_name": "PM-Agent",
  "owner_user_id": 1,
  "schema_version": "1.0.0",
  "generated_at": "2026-07-19T10:00:00",
  "updated_at": "2026-07-19T10:00:00",
  "storage": {
    "provider": "minio",
    "bucket": "pm-agent",
    "object_prefix": "PM-AGENT/1/10/",
    "index_path": "system/index.json"
  },
  "summary": {
    "total_nodes": 0,
    "active_files": 0,
    "fail_nodes": 0
  },
  "project": [],
  "user": [],
  "upload_failures": [],
  "system": {
    "index": "system/index.json",
    "file_details": "system/file_details/"
  }
}
~~~

## 5. 文件存储字段的写入时机

### 5.1 MinIO 上传前

MySQL 文件行只保存：

- 项目、上传请求和前端文件 ID；
- 业务类型和逻辑相对路径；
- 文件名、扩展名、大小、源修改时间和 MIME；
- `path_hash`、`quick_fingerprint` 和 `content_hash`；
- `status = uploading`；
- `upload_status = not_uploaded`。

以下字段必须为空：

~~~text
storage_uuid
storage_name
object_key
minio_path
detail_ref
~~~

### 5.2 MinIO 上传成功后

Java 在线程任务中生成临时存储身份并上传。只有 MinIO 返回成功后，才在数据库事务中回填：

~~~text
storage_uuid
storage_name
object_key
minio_path
detail_ref
status = active
upload_status = success
~~~

### 5.3 上传失败

- 不更新文件行；
- 文件继续保持 `not_uploaded`；
- 失败信息只进入当前接口返回的 `failedFiles[]`；
- 下一轮重试复用同一文件行；
- 第三轮结束后，仍为 `not_uploaded` 的文件进入索引失败列表。

## 6. 对象命名

成功上传时生成：

~~~text
storageUuid = 16 位随机十六进制值
storageName = {文件主名}-{storageUuid}.{扩展名}
objectKey = PM-AGENT/{ownerUserId}/{projectId}/{businessCode}/{storageName}
minioPath = {businessCode}/{storageName}
detailRef = system/file_details/{storageName}
~~~

在 MySQL 更新失败时，重试可以生成新的存储身份。由此产生的旧对象属于可接受的冗余数据。

## 7. 最终索引重建

### 7.1 触发条件

只有上传请求同时满足以下条件时触发：

1. 本轮预注册批次数与状态为 `completed` 的批次数都等于请求表中的 `round_total_batches`；
2. 文件事实行总数等于 `original_total_files`，且 `success + not_uploaded = original_total_files`；
3. `not_uploaded = 0`，或当前请求已经完成第三轮。

前两轮存在失败、单个批次完成或单个文件成功时均不得重建索引。

### 7.2 同步处理

~~~mermaid
flowchart TD
    A["查询本轮预注册与 completed 批次数"] --> B{"两者是否都等于 round_total_batches"}
    B -->|否| C0["请求保持 uploading"]
    B -->|是| C1["查询文件事实总数、success 与 not_uploaded"]
    C1 --> C1A{"事实总数和状态分布<br/>是否完整"}
    C1A -->|否| C1B["按数据冲突拒绝进入终态"]
    C1A -->|是| C2{"本轮结果"}
    C2 -->|全部成功| C3["请求状态 completed"]
    C2 -->|仍失败且未满三轮| C4["请求状态 awaiting_retry<br/>不重建索引"]
    C2 -->|第三轮仍失败| C5["请求状态 completed_with_failures"]
    C3 --> C["按 projectId 查询 MySQL 全部当前文件"]
    C5 --> C
    C --> D["success 文件构造 project/user 项"]
    C --> E["not_uploaded 文件构造 upload_failures"]
    D --> F["在内存生成完整 index.json"]
    E --> F
    F --> G["同步 PUT 固定 system/index.json"]
    G --> H{"PUT 是否成功"}
    H -->|是| I["写 index_rebuilt_at<br/>接口成功"]
    H -->|否| J["index_rebuilt_at 保持 NULL<br/>接口失败"]
~~~

重建原则：

- 不读取旧索引做增量合并；
- 不调用 MinIO `list` 或 `stat` 判断业务状态；
- 不在数据库事务中调用 MinIO；
- 单次重建只执行一次完整 `PUT`；
- 重复执行仍覆盖同一固定对象。
- 请求状态在重建前已经是 `completed` 或 `completed_with_failures`；
- 索引失败不增加请求状态，使用“终态且 `index_rebuilt_at IS NULL`”判断待恢复。

### 7.3 失败列表

`upload_failures` 只来自 MySQL 中最终仍为 `not_uploaded` 的文件，至少包含：

~~~json
{
  "file_id": 101,
  "relative_path": "backend/src/main/App.java",
  "upload_status": "not_uploaded"
}
~~~

接口中的临时错误消息不作为索引事实来源。

## 8. 冗余对象清理

当前上传热路径不执行复杂补偿。

后续清理任务可以：

1. 从 MySQL 查询全部非空有效 `object_key`；
2. 分页列出 MinIO 项目前缀下的普通文件对象；
3. 排除 `system/index.json` 和其他系统对象；
4. 删除长期不被 MySQL 引用的对象；
5. 记录清理日志和 `traceId`。

清理功能属于后续任务，当前不得描述为已实现。

## 9. Python 解析扩展点

当前阶段不发布文件解析消息、不创建文件业务队列，也不写 Outbox。

未来只能在下列条件全部满足后接入 Python：

1. 上传请求已完成；
2. `index.json` 同步重建成功；
3. 文件 `upload_status = success`；
4. 消息协议、幂等、重试和死信设计已经单独评审。

`ProjectFileUploadCompletionService` 是未来接入点，当前实现只同步调用索引重建并写 `index_rebuilt_at`，没有 MQ 副作用。

## 10. 一致性取舍

| 场景 | 当前取舍 |
|---|---|
| MySQL 成功、MinIO 失败 | 文件保持 `not_uploaded`，由前端下一轮重试 |
| MinIO 成功、MySQL 更新失败 | 允许出现冗余对象，文件仍为 `not_uploaded` |
| 索引重建失败 | 文件事实与请求终态不回滚，接口失败且 `index_rebuilt_at` 保持 NULL |
| 重复索引重建 | 从 MySQL 全量构造并覆盖固定对象 |
| RabbitMQ 不可用 | 不影响当前上传和索引链路 |

## 11. 验收标准

1. 项目 `active` 前固定位置已存在合法初始索引。
2. 文件 `not_uploaded` 时所有 MinIO 存储字段为空。
3. MinIO 上传成功后才回填存储字段。
4. 上传失败不更新文件行。
5. 前两轮失败不会触发索引重建。
6. 最终重建只读取 MySQL 业务事实。
7. 成功文件与失败文件正确进入不同索引数组。
8. 冗余 MinIO 对象不会影响上传完成判断。
9. 当前链路不依赖 RabbitMQ、Outbox 或 Python。
10. 请求状态只使用四种当前值，索引失败不增加额外状态。

## 12. 待确认问题

暂无。Python 解析和冗余对象定时清理在进入实施前分别补充专项设计。
