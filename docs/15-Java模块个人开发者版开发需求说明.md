# Java模块认证与项目文件基座说明

## 1. 背景

Java 模块是无租户隔离的多用户后端基座，在账户认证之上加入最小项目归属和 MinIO 项目文件能力。项目文件批次上传、V12 数据模型和同步索引重建已经落地，详细规则以 [18-项目文件批次上传模块设计](./18-项目文件可靠上传模块设计.md) 为准。

## 2. 目标

1. 保留common、auth、user、最小project、file、infrastructure和必要配置；
2. 数据库保留用户、最小项目、项目文件、上传请求和物理批次表；
3. 支持多个用户使用唯一邮箱登录；
4. 删除租户、逻辑删除、文件版本和未使用中间件；
5. 保持统一响应、异常、日志和 traceId；
6. 使用 Lombok 简化构造器注入和日志门面。

## 3. 当前能力

- 用户注册；
- 邮箱密码登录和退出；
- 当前用户的用户名、邮箱和密码修改；
- 健康检查；
- 统一响应、错误码、全局异常和访问日志；
- Sa-Token JWT、MyBatis Plus、Flyway、Knife4j。
- 最小项目文件空间创建和查询；
- MinIO 批次文件上传、已有文件同对象键覆盖、路径修改、只读地址和删除；
- 快速指纹、内容SHA-256和上传失败状态。

已落地的批次上传能力：

- 前端空目录处理、文件筛选，按最多 50 个文件且原始文件总大小不超过 240 MB 分批，并在同一轮逐批顺序调用；
- 后端批次内多线程上传，MySQL 已成功文件不重复 PUT；
- 首次落库为 `not_uploaded` 且存储字段为空；
- 前端首轮加最多两轮失败重试；
- 请求级完成闸门，包括批次计数、文件事实总数和状态分布校验；
- 已完成批次内容校验与 `processing` 超时同幂等键接管；
- 最终同步重建 `index.json`。

当前批次上传不包含完整项目管理、任务、Agent 文件解析、文件业务 RabbitMQ、Transactional Outbox、RBAC、组织、租户或文件历史版本。RabbitMQ 只保留基础配置。

## 4. 数据库规则

- 当前 MySQL 已有 `pm_user`、`pm_project`、`pm_project_file`、`pm_project_file_upload_request` 和物理导入批次等表；
- `pm_project_file_upload_request` 保存根请求，`pm_project_file_ingest_batch` 保存 manifest 预注册的物理批次；
- 不新增逐轮文件明细表，同一逻辑文件只保留一条 `pm_project_file`；
- 用户名和邮箱分别全局唯一；
- 邮箱是登录标识；
- 不限制用户数量；
- 不保留 `single_account_key`、`display_name`、`mobile`、`tenant_id`、`deleted`、`created_by` 或 `updated_by`；
- 历史 Flyway migration 不直接修改；新版模型由 V12 migration 落地；
- 新批次上传链路不读写历史 `pm_event_outbox`。

## 5. 编码规则

- Controller 负责业务入口和成功日志；
- `GlobalExceptionHandler` 负责失败日志；
- `TraceInterceptor` 负责访问日志和耗时；
- 依赖注入使用 `final` 字段和 `@RequiredArgsConstructor`；
- 日志类使用 `@Slf4j`；
- DTO 与实体转换继续使用 MapStruct；
- 不记录密码、密码哈希、邮箱、token 或完整敏感请求体。

## 6. 验证要求

```bash
cd backend
mvn clean test
mvn package
```

每次变更至少验证：

- 多用户注册成功；
- 重复用户名、邮箱被拒绝；
- 邮箱登录成功和失败分支；
- 用户资料和密码修改；
- Flyway创建认证与项目文件表；
- 空目录不调用后端；
- 51 个普通小文件被拆成 50 和 1 两批并顺序提交；
- 加入下一文件会使单批原始文件总大小超过 240 MB 时提前拆批，后端 256 MB 请求上限不被触发；
- 首次文件落库的 MinIO 存储字段为空；
- 当前轮失败不更新文件行；
- 重试复用同一文件行；
- 请求级闸门在全部成功或第三轮结束时只触发一次同步索引重建；
- RabbitMQ 停止时不影响当前上传和索引链路；
- traceId 同时出现在响应头、响应体和日志上下文。

## 7. 风险与取舍

| 风险 | 处理 |
|---|---|
| 邮箱大小写导致重复 | 所有邮箱写入和查询前统一转小写 |
| 旧前端仍发送用户名登录 | 前端联调时改为 `email + password` |
| 旧数据库迁移历史冲突 | 明确重置数据库，不兼容旧业务表 |
| 后续错误引入租户字段 | 项目技能明确禁止未经确认添加租户设计 |

## 8. 验收标准

- Java主代码保留认证基座，并增加最小project、file和MinIO infrastructure；
- 邮箱是唯一登录标识；
- 数据库允许多个用户，不包含单用户限制；
- Controller 使用 Lombok 并输出业务日志；
- 状态、business、动作和来源字段使用Java枚举；
- 批次上传代码不得发布文件业务 MQ 或写 Outbox；
- `mvn clean test` 和 `mvn package` 成功。

## 9. 待确认问题

暂无。
