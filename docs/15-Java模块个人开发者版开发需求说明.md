# Java模块认证与项目文件基座说明

## 1. 背景

Java模块是无租户隔离的多用户后端基座，在账户认证之上加入最小项目归属和MinIO项目文件能力。

## 2. 目标

1. 保留common、auth、user、最小project、file、infrastructure和必要配置；
2. 数据库保留用户、最小项目、项目文件和上传追踪表；
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
- MinIO单文件上传、同对象键覆盖、路径修改、只读地址和删除；
- 快速指纹、内容SHA-256和上传失败状态。

不包含完整项目管理、任务、Agent、RabbitMQ、outbox、RBAC、组织、租户或文件历史版本。

## 4. 数据库规则

- MySQL包含`pm_user`、`pm_project`、`pm_project_file`和上传追踪表；
- 用户名和邮箱分别全局唯一；
- 邮箱是登录标识；
- 不限制用户数量；
- 不保留 `single_account_key`、`display_name`、`mobile`、`tenant_id`、`deleted`、`created_by` 或 `updated_by`；
- Flyway使用V1创建用户表，V2创建项目文件表。

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
- 内容更新保持同一个`object_key`；
- 路径更新不调用MinIO；
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
- `mvn clean test` 和 `mvn package` 成功。

## 9. 待确认问题

暂无。
