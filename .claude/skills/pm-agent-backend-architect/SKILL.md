---
name: pm-agent-backend-architect
description: Java backend architecture skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user designs Spring Boot backend layering, API conventions, authentication and authorization, exception handling, business services, module boundaries, Java-Python service collaboration, or backend implementation plans for PM-Agent.
metadata:
  status: active
  language: en-US
  owner_module: backend
  related_docs:
    - docs/01-开发规划.md
    - docs/02-技术选型.md
    - docs/05-接口规范.md
---

# PM-Agent Backend Architecture Skill

## Trigger scenarios

Use this skill when the user asks for any of the following:

- Designing or reviewing Spring Boot backend layers, package structure, and module boundaries;
- Designing REST APIs, error codes, unified responses, and trace propagation;
- Designing authentication/authorization with Sa-Token, permission rules, and audit entry points;
- Designing Java and Python Agent service collaboration through HTTP or MQ;
- Designing backend implementation for business modules such as project, requirement, task, iteration, risk, or report;
- Evaluating whether backend changes comply with the red lines and phase constraints in `CLAUDE.md`.

## Goal

Help Claude design a stable, clear, evolvable Java backend architecture for PM-Agent. Keep module boundaries controlled and reduce later rework. Outputs must be directly implementable in the `backend/` project and should avoid generic advice.

---

## 1. Technical baseline (locked; do not replace without confirmation)

| Item | Choice | Notes |
|---|---|---|
| Language | Java 17+ | Required by Spring Boot 3 |
| Framework | Spring Boot 3 | |
| ORM | MyBatis Plus | With code generator and interceptors |
| Authentication | **Sa-Token + JWT mode** | Do not use Spring Security; do not introduce OAuth2 |
| API docs | Knife4j / OpenAPI 3 | |
| Database | MySQL 8 | Phase 1; vector storage may be introduced later if needed |
| Validation | Jakarta Validation | |
| Utilities | Hutool + MapStruct | Prefer Hutool; DTO conversion must use MapStruct |
| Package root | `com.ning.pm.<module>` | |

Any request to change the choices above must be confirmed with the user first. The skill must not decide such changes on its own.

---

## 2. Package structure and layering

### 2.1 Layers: traditional three layers plus local rich-domain methods where useful

```text
com.ning.pm
├── common                Unified response, exceptions, error-code enum, utilities
├── config                Spring config, Sa-Token config, MyBatis Plus config
├── infrastructure        External collaboration: Python Agent client, MQ, Redis, files
├── <module>              Business module: project / task / requirement / risk / ...
│   ├── controller        API entry points
│   ├── service           Business orchestration (mostly anemic services)
│   ├── domain            Entities / DOs and rich methods for key entities
│   ├── repository        MyBatis Plus mappers
│   ├── converter         MapStruct converters (DTO ↔ Entity)
│   └── dto               Request / response / internal transfer objects
```

### 2.2 When to use rich-domain methods

Default to anemic services for CRUD, list queries, and thin field updates.

Allow rich-domain methods when any of the following applies:

1. **State machine**: the entity has legal state transition rules, such as `Task.start()`, `Task.block(reason)`, or `Task.done()`;
2. **Business invariant**: multiple fields must be changed or validated together, such as `Risk.recalculateScore()` updating both `score` and `level`;
3. **Cross-field calculation**: the entity owns derived attributes that external code should not mutate through setters, such as `Iteration.progressPercent()`.

Do not put repository calls, external service calls, or operations on other entities inside rich-domain methods. Those remain service orchestration responsibilities.

### 2.3 Naming conventions

| Type | Suffix | Example |
|---|---|---|
| API entry | `Controller` | `TaskController` |
| Business service | `Service` / `ServiceImpl` | `TaskService` / `TaskServiceImpl` |
| Data access | `Mapper` | `TaskMapper` |
| Data entity | No suffix; use domain name | `Task`, `Project` |
| Request DTO | `Request` | `CreateTaskRequest` |
| Response DTO | `Response` or `VO` | `TaskDetailResponse` |
| Internal DTO | `DTO` | `TaskAssignDTO` |
| Converter | `Converter` | `TaskConverter` |

### 2.4 DTO and entity conversion with MapStruct

1. All pure DTO ↔ Entity field copying must use MapStruct. Do not write setter chains in Service or Controller code.
2. Each business module keeps its `XxxConverter` interface under `<module>/converter/`:

   ```java
   @Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
   public interface TaskConverter {
       Task toEntity(CreateTaskRequest request);
       TaskDetailResponse toResponse(Task entity);
       void updateEntity(@MappingTarget Task entity, UpdateTaskRequest request);
   }
   ```

3. `unmappedTargetPolicy = ERROR` is mandatory so missing target fields fail at compile time instead of silently dropping new fields.
4. The only allowed manual conversion exception is when conversion needs another Service / Repository, such as resolving `assigneeId` to `assigneeName`. In that case, the Service may manually assemble the combined fields, but same-name field copying still belongs in the Converter.
5. Converters must be Spring beans with `@Mapper(componentModel = "spring")`; do not use `Mappers.getMapper(...)`, because bean registration improves testability.

---

## 3. API conventions

### 3.1 Paths and versions

1. All business APIs must use the version prefix: `/api/v1/<module>/<resource>`.
2. v1 is active from the MVP stage. When future breaking changes are needed, create `/api/v2/`; do not make incompatible changes inside v1.
3. Internal health checks, monitoring, docs, and non-business APIs may use `/internal/`, `/actuator/`, `/doc.html` without the v1 prefix.
4. Python Agent service APIs should also follow `/api/v1/agent/<resource>` and be managed through a unified Java `AgentClient` baseUrl.

### 3.2 Unified response structure

```json
{
  "code": 0,
  "message": "成功",
  "data": {},
  "traceId": "abc123def456..."
}
```

- `code = 0` means success; non-zero codes are errors.
- `data` may be `null` on failure.
- `traceId` must be returned in every case, including exception responses.

### 3.3 traceId rules: optional frontend input, backend fallback

1. The backend interceptor reads `X-Trace-Id` from the request header.
2. If the frontend sends it, pass it through. If not, generate a UUID without hyphens.
3. Inject traceId into MDC so all business logs, exception logs, and Agent invocation logs include it.
4. When Java calls the Python Agent service, include `X-Trace-Id` in the HTTP header. Python must pass it through to LLM logs and the `agent_trace` table.

### 3.4 Error codes

- Manage all error codes in `common.errorcode.ErrorCode`.
- Follow the segments defined in `CLAUDE.md` section 4.4: 0 / 1xxxx / 2xxxx / 3xxxx / 4xxxx / 5xxxx / 9xxxx.
- Maintain every error code in the error-code table in `docs/05-接口规范.md`.
- Business errors should throw `BizException(ErrorCode, args...)`; a global `@RestControllerAdvice` handles fallback.
- Validation failures (`MethodArgumentNotValidException`) map to `10001`; the message should include the first invalid field.

---

## 4. Logging conventions

### 4.1 Required fields

All business logs use SLF4J + Logback. Every log line's MDC must include the following fields, injected by a global interceptor so business code does not need to set them manually:

| Field | Source | Notes |
|---|---|---|
| `traceId` | Request header or backend UUID fallback | Full-chain unique ID |
| `userId` | `StpUtil.getLoginIdAsLong()` | `-` when unauthenticated |
| `tenantId` | `BaseEntity.tenantId` or request header | Fixed to `0` in Phase 1 |
| `action` | Controller annotation or interceptor parsing | e.g. `task.create` |
| `costMs` | Calculated by interceptor during response | API duration |

### 4.2 Log format

```text
%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level [%X{traceId}] [%X{userId}] [%X{tenantId}] [%X{action}] %logger{36} - %msg costMs=%X{costMs}%n
```

### 4.3 Log level rules

| Level | Use case |
|---|---|
| `ERROR` | System exceptions, external service unavailable, uncaught exceptions |
| `WARN` | Business exceptions, validation failures, degradation triggered |
| `INFO` | API entry/exit, key state transitions, Agent invocation input/output summaries |
| `DEBUG` | Development only: detailed branches, SQL, full Prompt text |

### 4.4 Prohibited logging practices

- Do not use `System.out.println` or `e.printStackTrace`.
- Do not print full request bodies at INFO level. Sensitive fields such as passwords, tokens, or full Prompts must be masked.
- Do not write INFO logs inside loops. Use DEBUG or aggregate before logging.

Project docs under `docs/` are governed stylistically by `pm-agent-doc-writer`; logging/API field conventions are governed by this skill.

---

## 5. Authentication and authorization

1. Login state uses Sa-Token + JWT mode. Tokens go to Redis when Redis is introduced in Phase 2. Before then, Sa-Token in-memory mode is acceptable for development.
2. RBAC (role-permission-user) is introduced in Phase 2. Phase 1 MVP distinguishes only authenticated vs unauthenticated users.
3. Use `@SaCheckLogin` and `@SaCheckPermission("project:edit")`; do not hand-write authorization checks in Services.
4. Get the current user through a wrapper such as `CurrentUserHolder` around `StpUtil.getLoginIdAsLong()`. Do not call static methods directly in Controllers, because the wrapper is easier to mock in tests.

---

## 6. Multi-tenancy reservation (not enabled in Phase 1)

1. All business tables should include `tenant_id BIGINT NOT NULL DEFAULT 0` from Phase 1 table design onward.
2. `BaseEntity` includes `tenantId`, defaulting to `0`.
3. Configure MyBatis Plus `TenantLineInnerInterceptor`, but disable it with `pm.tenant.enabled=false`.
4. When SaaS is launched later, enable the switch, add tenant resolution from JWT or subdomain, and backfill tenant ownership. No SQL or Mapper rewrite should be needed.
5. Document this convention at the top of `docs/04-数据模型.md` so future tables do not miss it.

---

## 7. Java ↔ Python Agent service collaboration

### 7.1 Channel selection: HTTP + MQ combination

| Scenario | Channel | Reason |
|---|---|---|
| Agent Q&A, intent recognition, requirement decomposition with streaming/second-level return | **HTTP** (sync / SSE) | The user waits in the frontend and needs real-time feedback |
| Weekly report generation, document vectorization, batch risk scanning, scheduled tasks | **MQ** after RabbitMQ in Phase 5 | Long-running, retryable, non-blocking |
| MVP Phase 3-4 before MQ | HTTP for all | Simulate async by returning task ID first and polling a task table |

### 7.2 Invocation rules

1. Java must wrap a unified `AgentClient` based on WebClient or Spring `RestClient`; business Services must not directly create HTTP clients.
2. Every call must include `X-Trace-Id`, `X-User-Id`, and `X-Tenant-Id`, even when tenant is 0.
3. Timeouts and retries: default HTTP connect timeout 2s / read timeout 30s, except streaming APIs. Do not auto-retry failures; let business logic decide.
4. Failure handling: non-2xx Agent service responses throw `AgentException` in the 4xxxx error-code range. Agent failures must not affect the main business transaction; transaction boundaries must stay outside Agent calls.
5. Structured input/output: Java-to-Python calls must use strongly typed DTOs. Do not use `Map<String, Object>`.

---

## 8. Exceptions, transactions, and idempotency

### 8.1 Exception hierarchy

- `BizException`, `AgentException`, and `SystemException` all extend `BaseException` and carry `ErrorCode`.
- `GlobalExceptionHandler` handles fallback and separates log levels: business exceptions as `WARN`, system exceptions as `ERROR`.

### 8.2 Transaction boundaries

- `@Transactional` should only be placed on Service methods. Avoid complex propagation settings across nested Services.
- External calls (Agent, MQ, HTTP) must not be inside transactions. Persist business changes first, then send external calls. If the external call must happen before persistence, use Spring transaction listeners or the outbox pattern when MQ is introduced in Phase 5.

### 8.3 Idempotency: frontend must send Idempotency-Key

1. All write APIs (`POST` / `PUT` / `PATCH` / `DELETE`) must carry `X-Idempotency-Key`. If missing, return `10002` for missing parameter.
2. The frontend should generate a UUID when entering the form or triggering the action, then reuse it until submission succeeds, including retries.
3. The backend interceptor uses `userId + API path + Idempotency-Key` as the Redis key with 10-minute TTL:
   - First request: pass through and cache the response after processing;
   - Hit: return the previous response directly without running business logic again.
4. When Agent calls business APIs, `AgentClient` automatically generates a UUID as the Idempotency-Key; business Services do not need to know.
5. Before Redis is introduced in Phase 1, use a local Caffeine temporary solution for single-instance idempotency; switch to Redis before production.

---

## 9. Audit logs (deferred; Phase 1 only reserves entry points)

Decision: Phase 1 does not implement a full audit log system. Add it as an enhancement after core business modules such as project, task, and risk are complete; coverage can be decided then.

Phase 1 reservations:

1. Add an empty `@AuditLog(action="task.create", resource="task")` annotation under `common`, with a placeholder AOP aspect to avoid missing annotations later.
2. Mark audit logs as “Phase 7 or earlier, TBD” in `docs/01-开发规划.md` and `docs/02-技术选型.md`.
3. Agent Trace is not part of this deferment. The `agent_trace` table must land in Phase 3 because Agent autonomous decisions are not traceable without it.

---

## 10. Module design output format

When designing a single business module, such as task management, output this structure:

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

Keep output headings and user-facing content in Chinese according to project language rules.

---

## 11. Workflow

When designing or reviewing a backend task:

1. Align with the phase in `CLAUDE.md` section 5. If a capability is beyond the phase, mark it as later and do not implement it now.
2. Check technical red lines. If a new middleware or framework is needed, stop and ask the user first.
3. Reuse existing patterns. Check whether similar modules already exist before designing new ones.
4. Output the plan using the module design format above.
5. List gaps. When information is insufficient, put it under “待确认问题”; do not hide gaps behind defaults.
6. Move in small steps. Keep each task to one module; split cross-module work before implementation.

---

## 12. Boundaries that require user confirmation

Ask the user before doing any of the following:

- Introducing new middleware, frameworks, databases, or message systems;
- Replacing or bypassing Sa-Token authentication;
- Bypassing MapStruct by hand-writing full DTO conversion blocks;
- Making external calls inside transactions;
- Hand-writing authorization checks in business Services instead of using Sa-Token annotations;
- Implementing future-phase features early, such as Redis cluster in Phase 1 or RAG in Phase 2;
- Changing the `com.ning.pm` package root, unified response structure, error-code segments, or `/api/v1/` prefix;
- Skipping “待确认问题” and directly outputting a plan when key information is missing.
