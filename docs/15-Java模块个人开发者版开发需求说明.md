# Java 模块认证与项目文件基座说明

## 1. 背景

Java 模块是无租户隔离的多用户后端基座，在账户认证之上提供最小项目归属和 MinIO 项目文件能力。当前项目文件上传使用最简单的单文件链路，详细规则以 [18-项目文件可靠上传模块设计](./18-项目文件可靠上传模块设计.md) 为准。

## 2. 目标

1. 保留 `common`、`auth`、`user`、最小 `project`、`file`、`infrastructure` 和必要配置；
2. 数据库保留用户、最小项目和项目文件表；
3. 支持多个用户使用唯一邮箱登录；
4. 保持统一响应、异常、日志和 traceId；
5. 使用简单、可验证的单文件上传实现，不引入批次编排。

## 3. 当前能力

- 用户注册、邮箱密码登录和退出；
- 当前用户资料和密码修改；
- 健康检查、统一响应、错误码、全局异常和访问日志；
- Sa-Token JWT、MyBatis Plus、Flyway、Knife4j；
- 最小项目创建和查询；
- 项目创建时同步初始化 `system/index.json`；
- MinIO 单文件上传、已有文件覆盖、路径修改、只读地址和删除；
- 快速指纹、内容 SHA-256 和文件上传状态；
- 文件解析占位接口。

单文件上传能力：

- 前端逐文件校验并顺序调用接口；
- 当前流程不自动重试，失败文件只提示后续更新项目；
- Java 先插入 `uploading / not_uploaded` 文件记录；
- Java 对当前文件执行一次 MinIO PUT；
- 成功后更新为 `active / success`；
- 失败时不更新数据库记录，向前端返回文件级失败；
- 单文件上传不改写 `index.json`；
- 文件队列结束后，前端调用暂未实现业务的解析接口。

当前链路不包含文件批次、完整 Agent 文件解析、文件业务 RabbitMQ、Transactional Outbox、RBAC、组织、租户或文件历史版本。

## 4. 数据库规则

- 当前核心表包括 `pm_user`、`pm_project` 和 `pm_project_file`；
- Flyway 只保留 V1，直接创建三张当前核心表；
- 同一逻辑文件只保留一条 `pm_project_file`；
- 用户名和邮箱分别全局唯一，邮箱是登录标识；
- 不限制用户数量；
- 不保留 `single_account_key`、`display_name`、`mobile`、`tenant_id`、`deleted`、`created_by` 或 `updated_by`；
- V1 不创建批次表、任务旧表、Outbox 表或演示数据；
- 已执行旧迁移的开发数据库需要重建为空 schema 后再启动。

## 5. 编码规则

- Controller 负责业务入口；
- `GlobalExceptionHandler` 负责失败日志；
- `TraceInterceptor` 负责访问日志和耗时；
- 依赖注入使用 `final` 字段和 `@RequiredArgsConstructor`；
- 日志类使用 `@Slf4j`；
- DTO 与实体转换继续使用 MapStruct；
- 不记录密码、密码哈希、token 或完整敏感请求体；
- 文件上传实现不增加批次、线程池、完成闸门或内部重试。

## 6. 验证要求

```bash
cd backend
mvn test
mvn package
```

每次相关变更至少验证：

- 项目创建仍初始化 `system/index.json`；
- 单文件首次落库为 `uploading / not_uploaded`；
- 数据库插入发生在 MinIO PUT 前；
- MinIO 成功后更新为 `active / success`；
- MinIO 失败后不执行数据库更新；
- 单文件上传不触发索引重建；
- 解析占位接口不调用 MinIO、MQ 或 Python；
- RabbitMQ 停止时不影响当前上传链路；
- traceId 同时出现在响应头、响应体和日志上下文。

## 7. 风险与取舍

| 风险 | 当前处理 |
|---|---|
| MinIO 成功但数据库状态更新失败 | 返回失败，允许暂时存在冗余对象，后续更新项目处理 |
| 上传失败记录长期为 `not_uploaded` | 由后续更新项目业务接管，不在首次上传流程恢复 |
| 解析接口尚无业务实现 | 仅保留稳定入口，不提前引入 MQ 或 Python 编排 |
| 旧数据库已执行 V1～V13 | 开发环境备份后重建空 schema；生产或共享库单独制定迁移方案 |

## 8. 验收标准

- Java 主代码保留认证、最小项目、文件和 MinIO 基座；
- 邮箱是唯一登录标识，数据库允许多个用户；
- 旧批次上传业务代码已删除；
- 单文件上传顺序符合先落库、后 MinIO、成功再更新状态；
- 上传接口不发布文件业务 MQ、不写 Outbox、不改写索引；
- 解析接口存在但没有解析业务实现；
- `mvn test` 和 `mvn package` 成功。

## 9. 待确认问题

暂无。
