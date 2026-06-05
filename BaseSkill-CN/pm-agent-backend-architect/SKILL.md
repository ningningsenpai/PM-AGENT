---
name: pm-agent-backend-architect
description: 面向 PM-Agent 智能项目管理 Agent 平台的 Java 后端架构 Skill。每当用户设计 Spring Boot 后端分层、接口规范、权限认证、异常处理、业务服务、模块边界、Java 与 Python 服务协作或后端开发计划时，都应使用本 Skill。
metadata:
  status: active
  language: zh-CN
  owner_module: backend
  related_docs:
    - docs/01-开发规划.md
    - docs/02-技术选型.md
    - docs/05-接口规范.md
---

# PM-Agent 后端架构 Skill

## 触发场景

当用户提出以下类型请求时使用本 Skill：

- 设计或评审 Spring Boot 后端的分层、包结构、模块边界；
- 设计 REST 接口、错误码、统一响应、链路追踪；
- 设计认证授权（Sa-Token）、权限规则、审计接入点；
- 设计 Java 与 Python Agent 服务的协作方式（HTTP / MQ）；
- 设计某个业务模块（项目、需求、任务、迭代、风险、报告等）的后端开发方案；
- 评估后端改动是否符合 CLAUDE.md 中的红线与阶段约束。

## 目标

帮助 Claude 为本项目设计稳定、清晰、可演进的 Java 后端架构，控制模块边界，减少后期重构。所有产出必须可直接落到 `backend/` 工程中，避免泛泛而谈。

---

## 一、技术基线（已锁定，不得擅自更换）

| 项 | 选型 | 备注 |
|---|---|---|
| 语言 | Java 17+ | Spring Boot 3 强制要求 |
| 框架 | Spring Boot 3 | |
| ORM | MyBatis Plus | 配合代码生成器与拦截器 |
| 认证 | **Sa-Token + JWT 模式** | 不使用 Spring Security、不引入 OAuth2 |
| API 文档 | Knife4j / OpenAPI 3 | |
| 数据库 | MySQL 8 | 第 1 阶段；后续如需向量再引入 pgvector 子库 |
| 校验 | Jakarta Validation | |
| 工具库 | Hutool + MapStruct | 优先 Hutool；DTO 转换强制走 MapStruct |
| 包名根 | `com.ning.pm.<module>` | |

> 任何更换上表选型的需求，必须先和用户确认，禁止 Skill 自行决定。

---

## 二、包结构与分层

### 2.1 分层（传统三层 + 关键实体局部充血）

```text
com.ning.pm
├── common                通用响应、异常、错误码枚举、工具
├── config                Spring 配置、Sa-Token 配置、MyBatis Plus 配置
├── infrastructure        外部协作：Python Agent 客户端、MQ、Redis、文件
├── <module>              业务模块（project / task / requirement / risk / ...）
│   ├── controller        接口入口
│   ├── service           业务编排（贫血服务）
│   ├── domain            实体（Entity / DO）、关键实体的充血方法
│   ├── repository        MyBatis Plus Mapper
│   ├── converter         MapStruct 转换器（DTO ↔ Entity）
│   └── dto               请求 / 响应 / 内部传输对象
```

### 2.2 何时充血（不可滥用）

**默认贫血**：CRUD、列表查询、字段更新等业务规则薄的场景，全部走 Service。

**允许充血**的判定条件（任一满足即可）：

1. **状态机**：实体存在合法状态迁移规则（如 `Task.start()`、`Task.block(reason)`、`Task.done()`）；
2. **业务不变量**：实体内部多个字段必须同时变更或同时校验（如 `Risk.recalculateScore()` 同时改 `score` 和 `level`）；
3. **跨字段计算**：实体上有派生属性，外部不应直接 setter（如 `Iteration.progressPercent()`）。

**禁止**把"调用其他实体 / 调用 Repository / 调用外部服务"放进充血方法——这些仍属于 Service 编排职责。

### 2.3 命名约定

| 类型 | 后缀 | 示例 |
|---|---|---|
| 接口入口 | `Controller` | `TaskController` |
| 业务服务 | `Service` / `ServiceImpl` | `TaskService` / `TaskServiceImpl` |
| 数据访问 | `Mapper` | `TaskMapper` |
| 数据实体 | 无后缀（领域名）| `Task`、`Project` |
| 请求 DTO | `Request` | `CreateTaskRequest` |
| 响应 DTO | `Response` 或 `VO` | `TaskDetailResponse` |
| 内部 DTO | `DTO` | `TaskAssignDTO` |
| 转换器 | `Converter` | `TaskConverter` |

### 2.4 DTO 与实体转换（强制 MapStruct）

1. **所有 DTO ↔ Entity 的纯字段搬运必须通过 MapStruct 完成**，禁止在 Service / Controller 里手写 setter 链式赋值；
2. 每个业务模块在 `<module>/converter/` 下维护对应的 `XxxConverter` 接口：

   ```java
   @Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
   public interface TaskConverter {
       Task toEntity(CreateTaskRequest request);
       TaskDetailResponse toResponse(Task entity);
       void updateEntity(@MappingTarget Task entity, UpdateTaskRequest request);
   }
   ```

3. `unmappedTargetPolicy = ERROR` 强制开启——目标字段漏映射时编译报错，避免新增字段时静默丢失；
4. **唯一允许手写转换的例外**：转换过程中需要调用其他 Service / Repository（如 `assigneeId → assigneeName` 需要查用户表），此时在 Service 里手写组装"组合字段"部分，但"同名字段搬运"仍交给 Converter，禁止整段手写；
5. Converter 必须以 `@Mapper(componentModel = "spring")` 注册为 Bean，禁止使用 `Mappers.getMapper(...)` 静态获取，便于单测替身。

---

## 三、API 规范

### 3.1 路径与版本

1. **所有业务接口必须带版本号前缀**：`/api/v1/<module>/<resource>`；
2. v1 在 MVP 阶段即生效，未来出现 breaking 变更时新开 `/api/v2/`，**禁止在 v1 内做不兼容修改**；
3. 内部健康检查、监控、文档（Knife4j、actuator）等非业务接口不带 v1 前缀，挂在 `/internal/`、`/actuator/`、`/doc.html`；
4. Python Agent 服务接口同样遵循 `/api/v1/agent/<resource>`，由 Java `AgentClient` 统一管理 baseUrl。

### 3.2 统一响应结构

```json
{
  "code": 0,
  "message": "成功",
  "data": {},
  "traceId": "abc123def456..."
}
```

- `code = 0` 表示成功，非 0 为错误码（见 3.4）；
- `data` 失败时允许为 `null`；
- `traceId` 任何场景都必须返回，包括异常响应。

### 3.3 traceId 规则（前端非强制传入 + 后端兜底）

1. 后端拦截器读取请求头 `X-Trace-Id`；
2. 若前端传入则透传；若未传，后端用 UUID（去掉 `-`）生成；
3. traceId 通过 MDC 注入日志，所有业务日志、异常日志、Agent 调用日志均需携带；
4. Java 调用 Python Agent 服务时，必须在 HTTP Header 中带上 `X-Trace-Id`，Python 侧透传到 LLM 调用日志与 `agent_trace` 表。

### 3.4 错误码

- 错误码统一在 `common.errorcode.ErrorCode` 枚举类中管理；
- 错误码分段遵守 CLAUDE.md 第 4.4 节（0 / 1xxxx / 2xxxx / 3xxxx / 4xxxx / 5xxxx / 9xxxx）；
- 每个错误码必须同时维护到 `docs/05-接口规范.md` 的错误码表；
- 业务抛错统一用 `BizException(ErrorCode, args...)`，全局 `@RestControllerAdvice` 兜底；
- 校验失败（`MethodArgumentNotValidException`）映射为 `10001`，message 拼接第一个错误字段。

---

## 四、日志规范

### 4.1 强制字段

所有业务日志通过 SLF4J + Logback 输出，**每条日志的 MDC 必须携带以下字段**（由全局拦截器注入，业务代码无需手动塞）：

| 字段 | 来源 | 备注 |
|---|---|---|
| `traceId` | 请求头或后端 UUID 兜底 | 全链路唯一 |
| `userId` | Sa-Token `StpUtil.getLoginIdAsLong()` | 未登录时为 `-` |
| `tenantId` | `BaseEntity.tenantId` 或请求头 | 第 1 阶段固定 `0` |
| `action` | Controller 注解或拦截器自动解析 | 如 `task.create` |
| `costMs` | 拦截器在响应阶段计算 | 接口耗时 |

### 4.2 日志输出格式

```text
%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level [%X{traceId}] [%X{userId}] [%X{tenantId}] [%X{action}] %logger{36} - %msg costMs=%X{costMs}%n
```

### 4.3 日志级别约定

| 级别 | 使用场景 |
|---|---|
| `ERROR` | 系统异常、外部服务不可用、未捕获异常 |
| `WARN` | 业务异常、参数校验失败、降级触发 |
| `INFO` | 接口入口出口、关键状态迁移、Agent 调用入参出参摘要 |
| `DEBUG` | 仅开发环境，详细分支、SQL、Prompt 全文 |

### 4.4 禁止事项

- 禁止 `System.out.println` / `e.printStackTrace`；
- 禁止打印完整请求体到 INFO（密码、token、Prompt 全文等敏感字段须脱敏）；
- 禁止在循环内打 INFO 级别日志（用 DEBUG 或聚合后输出）。

> 项目文档（`docs/`）由 `pm-agent-doc-writer` Skill 负责风格统一，日志字段约定不在该 Skill 范围内，以本 Skill 为准。

---

## 五、认证与权限

1. **登录态**：Sa-Token + JWT 模式；token 放在 Redis（第 2 阶段引入 Redis 前，先用 Sa-Token 内存模式，开发期可接受）；
2. **权限模型**：第 2 阶段引入 RBAC（角色 - 权限 - 用户）；MVP 第 1 阶段仅区分"登录用户 / 未登录"；
3. **接口标注**：使用 `@SaCheckLogin` / `@SaCheckPermission("project:edit")` 注解，不在 Service 里手写鉴权；
4. **当前用户获取**：统一通过 `StpUtil.getLoginIdAsLong()` 包装为 `CurrentUserHolder`，禁止在 Controller 里直接调用静态方法获取，便于测试 mock。

---

## 六、多租户预留（第 1 阶段不启用）

1. **所有业务表**第 1 阶段建表时即添加 `tenant_id BIGINT NOT NULL DEFAULT 0`；
2. 实体基类 `BaseEntity` 包含 `tenantId` 字段，默认值 `0`；
3. MyBatis Plus 配置 `TenantLineInnerInterceptor`，但通过配置项 `pm.tenant.enabled=false` 关闭；
4. 上线 SaaS 时只需：开关置 `true` → 接入租户解析（从 JWT 或子域名）→ 数据回填租户归属。**不需要改任何 SQL 与 Mapper**；
5. 文档化：在 `docs/04-数据模型.md` 顶部说明此约定，避免后人建表时漏掉。

---

## 七、Java ↔ Python Agent 服务协作

### 7.1 通道选择规则（HTTP + MQ 结合）

| 场景 | 通道 | 理由 |
|---|---|---|
| Agent 问答、意图识别、需求拆解（流式或秒级返回） | **HTTP**（同步 / SSE） | 用户在前端等待结果，须实时反馈 |
| 周报生成、文档向量化、批量风险扫描、定时任务 | **MQ**（第 5 阶段引入 RabbitMQ 后） | 耗时长、可重试、不阻塞用户 |
| MVP 阶段（第 3~4 阶段，MQ 未引入） | 全部走 HTTP | 长耗时任务通过"先返回任务 ID + 前端轮询任务表"模拟异步 |

### 7.2 调用规范

1. Java 侧封装统一的 `AgentClient`（基于 WebClient 或 Spring `RestClient`），不允许业务 Service 直接 `new HttpClient`；
2. 所有调用必须传入 `X-Trace-Id`、`X-User-Id`、`X-Tenant-Id`（即使值为 0）；
3. **超时与重试**：HTTP 默认连接 2s / 读取 30s（流式接口除外），失败不自动重试，由业务侧决定；
4. **失败处理**：Agent 服务返回非 2xx 时抛 `AgentException`（错误码段 4xxxx），不影响主业务事务（事务边界须在 Agent 调用之外）；
5. **结构化输入输出**：Java 调 Python 必须用强类型 DTO，禁止 `Map<String, Object>`。

---

## 八、异常、事务与幂等

### 8.1 异常体系

- `BizException`（业务异常）/ `AgentException`（Agent 异常）/ `SystemException`（系统异常），全部继承 `BaseException`，携带 `ErrorCode`；
- 全局 `GlobalExceptionHandler` 兜底，区分日志级别（业务异常 `WARN`，系统异常 `ERROR`）。

### 8.2 事务边界

- `@Transactional` 只标注在 Service 方法上，禁止跨 Service 嵌套传播复杂的 propagation 设置；
- **外部调用（Agent、MQ、HTTP）禁止包在事务内**——先持久化业务变更，再发外部调用；如必须先调用再落库，使用 Spring 事务监听器或 outbox 模式（第 5 阶段引入 MQ 时配套）。

### 8.3 幂等（强制前端传 Idempotency-Key）

1. **所有写接口**（`POST` / `PUT` / `PATCH` / `DELETE`）**必须**由前端在请求头携带 `X-Idempotency-Key`，未携带直接返回 `10002`（参数缺失）；
2. key 推荐由前端在"进入表单 / 触发动作"那一刻生成 UUID，提交完成前保持不变（重试沿用同一 key）；
3. 后端拦截器以 `用户ID + 接口路径 + Idempotency-Key` 为 Redis 键，TTL 10 分钟：
   - 首次：放行，处理完后缓存响应；
   - 命中：直接返回上次响应，不再走业务逻辑；
4. **Agent 调用业务接口**时，由 `AgentClient` 自动生成 UUID 作为 Idempotency-Key，业务 Service 无需关心；
5. Redis 引入前（第 1 阶段），用本地 Caffeine 临时方案，仅保证单实例幂等；上线前必须切换到 Redis。

---

## 九、审计日志（延期到后续阶段，第 1 阶段仅留接入点）

> **决策**：第 1 阶段不实现完整审计日志体系。在主要业务（项目 / 任务 / 风险）完成后作为增强项推进，覆盖范围届时再敲定。

第 1 阶段需做的预留：

1. 在 `common` 下声明空注解 `@AuditLog(action="task.create", resource="task")`，AOP 切面留空实现，避免后续补注解时漏标；
2. `docs/01-开发规划.md` 与 `docs/02-技术选型.md` 标记"审计日志：第 7 阶段或更早，待定"；
3. **Agent Trace 不属于此延期范围**——`agent_trace` 表在第 3 阶段必须落地，原因：Agent 自主决策无 trace 即无法追溯。

---

## 十、模块设计输出格式

设计单个业务模块（如"任务管理"）时，必须按以下结构输出：

```markdown
# 后端设计：[模块名称]

## 模块职责
（一句话说清边界，写明不负责什么）

## 领域对象
- 实体清单与关键字段
- 是否充血、充血的方法及不变量

## 接口清单
| 方法 | 路径 | 说明 | 权限 | 错误码 |
|---|---|---|---|---|

## 请求 / 响应 DTO 与 Converter
（核心 DTO 字段表 + Converter 方法签名）

## 业务流程
（关键流程图或步骤，标出与 Agent、MQ、外部服务的交互）

## 异常处理
（业务异常清单 + 错误码 + 触发条件）

## 数据一致性
（事务边界、Idempotency-Key、并发场景）

## 与 Python Agent 的协作方式
（走 HTTP 还是 MQ；输入输出 DTO；超时与失败兜底）

## 开发步骤
（按依赖顺序列出可独立提交的小步骤）

## 验收标准
（接口 case、异常 case、权限 case、幂等 case）

## 待确认问题
（不要假设，必须列出空白点）
```

---

## 十一、工作流程

设计或评审一个后端任务时，按此顺序执行：

1. **对齐阶段**：确认当前任务属于 CLAUDE.md 第 5 节中的哪个阶段；超出阶段的功能直接标"待后续阶段"，不实现；
2. **对齐技术红线**：检查是否需要引入新中间件/框架，若需要先停下来询问用户；
3. **复用既有模式**：先检查同类模块是否已有实现（如项目模块的 CRUD 模式），新模块应保持一致；
4. **输出方案**：按第十节"模块设计输出格式"产出文档；
5. **列出空白**：信息不足时优先在"待确认问题"列出，禁止默认值掩盖空白；
6. **小步推进**：单次任务限定在一个模块；跨模块改动必须先拆分。

---

## 十二、不可越界（红线）

以下事项必须先经用户确认：

- 引入新的中间件、框架、数据库、消息系统；
- 替换或绕过 Sa-Token 的认证机制；
- 绕过 MapStruct 直接手写整段 DTO 转换；
- 在事务内做外部调用（Agent / HTTP / MQ）；
- 在业务 Service 里手写鉴权代替 Sa-Token 注解；
- 提前实现尚未到阶段的功能（如第 1 阶段引入 Redis 集群、第 2 阶段做 RAG）；
- 修改 `com.ning.pm` 包根、统一响应结构、错误码分段、`/api/v1/` 前缀；
- 跳过"待确认问题"环节直接出方案。
