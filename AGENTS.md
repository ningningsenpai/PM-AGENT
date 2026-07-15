# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 语言与协作规则

- 所有对话、项目文档、错误提示使用中文；代码注释也使用中文。
- 修改文件前必须先读取相关文件；涉及多模块改动时先列出计划再执行。
- 除非用户明确要求，不得新增、删除、改写、格式化或统一处理本次代码修改范围之外的注释。
- 不主动替换既定技术选型：前端 Vue 3 + Naive UI，后端 Spring Boot 3 + Sa-Token + MyBatis Plus，Agent 服务 FastAPI。
- 中间件按阶段引入，不提前加入未确认的 Redis、RabbitMQ、MinIO、向量库等运行依赖。
- 优先使用 `.Codex/skills/` 下的正式英文 Skill；`BaseSkill-CN/` 只作为中文参考，不作为正式开发调用来源。

## 常用命令

### 本地中间件

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs mysql
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

如需启动当前 Compose 中已配置的全部本地服务：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

重置本地数据会删除数据卷，执行前必须确认：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```

### 后端 Spring Boot

```bash
cd backend
mvn spring-boot:run
mvn test
mvn -Dtest=AuthControllerTest test
mvn -Dtest=AuthServiceImplTest#registerSuccess test
mvn package
```

后端默认端口为 `8080`，本地数据库连接读取 `PM_AGENT_DB_USERNAME`、`PM_AGENT_DB_PASSWORD`，未设置时使用 `pm_agent` / `pm_agent_dev`。Flyway 迁移位于 `backend/src/main/resources/db/migration/`，启动后自动执行。

### 前端 Vue 3

```bash
cd frontend
pnpm install
pnpm dev
pnpm typecheck
pnpm build
pnpm preview
```

前端开发服务默认端口为 `5173`，`vite.config.ts` 将 `/api` 代理到 `http://localhost:8080`。当前未配置前端测试脚本和 lint 脚本，不要虚构相关命令。

### Python Agent 服务

```bash
cd agent-service
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .
uvicorn app.main:app --reload --port 8000
python -m unittest tests/test_project_upload.py
python -m pytest app/project_context/tests/test_file_tree_scan.py
```

Agent 服务默认端口为 `8000`，后端通过 `PM_AGENT_SERVICE_BASE_URL` 调用，默认值为 `http://localhost:8000`。如本机未安装 `pytest`，优先补充开发依赖或使用已有 `unittest` 用例，不要把第三方包测试目录纳入测试范围。

## 架构总览

本仓库是 PM-Agent 智能项目管理平台的 Monorepo，核心链路为：

```text
Vue 3 前端 -> Spring Boot 业务后端 -> FastAPI Agent 服务 -> LLM / 工具 / 后续 RAG
```

- `frontend/`：Vue 3 + TypeScript + Vite + Naive UI。按业务模块组织在 `src/modules/`，公共请求封装在 `src/api/http.ts`，路由在 `src/router/index.ts`，登录态在 `src/stores/auth.ts`。
- `backend/`：Spring Boot 3 单体业务主系统。包名以 `com.ning.pm` 为根，通用能力在 `common/`，配置在 `config/`，业务按 `auth`、`user`、`project`、`task`、`agent` 等模块拆分。
- `agent-service/`：FastAPI Agent 服务。入口为 `app/main.py`，当前包含 Agent 对话、项目文件、LLM 适配、流式事件、项目上下文扫描等能力。
- `deploy/`：本地 Docker 中间件配置。业务表结构由后端 Flyway 管理，不放入 MySQL 容器初始化脚本。
- `docs/`：长期项目文档。涉及接口、数据模型、Agent 设计、部署或验收标准变化时，需要同步更新对应文档。

## 后端约定

- API 路径使用 `/api/v1/<module>/<resource>`，健康检查和 Knife4j 等非业务接口除外。
- 统一响应结构为 `R<T>`：`code`、`message`、`data`、`traceId`；错误码集中在 `common.errorcode.ErrorCode`。
- `TraceInterceptor` 负责 `X-Trace-Id` 生成与透传。
- 登录认证使用 Sa-Token + JWT；Controller 使用登录或权限注解，Service 不手写绕过式鉴权。
- MyBatis Plus 实体继承通用基础字段时遵循现有 `BaseEntity` 和自动填充配置；数据库表名使用小写下划线业务前缀。
- 新增或调整数据库结构必须新增 Flyway migration，不直接修改已应用的历史迁移。

## 前端约定

- HTTP 调用统一走 `src/api/http.ts` 的 `request<T>`，它会自动注入 `Authorization` 和 `X-Trace-Id`。
- 业务代码按模块放入 `src/modules/<module>/`，通常包含 `api.ts`、`types.ts`、`store.ts`、`mock.ts` 和 `pages/`。
- 路由守卫依赖 `useAuthStore()` 加载当前用户；新增受保护页面默认放在非 `meta.public` 路由下。
- 组件库使用 Naive UI；前端文件名使用 kebab-case，组件名使用大驼峰。
- UI 改动完成后应启动 `pnpm dev` 并在浏览器验证关键路径；如果无法实际验证，需要在交付说明中明确说明。

## Agent 服务约定

- Agent 不直接操作业务数据库；业务变更必须通过 Java 后端工具 API 完成。
- 高风险动作（删除、权限变更、对外通知等）必须人工确认。
- 模型输出优先结构化，并通过 Pydantic / JSON Schema 校验关键字段。
- Agent Trace、模型分层、成本控制策略以 `docs/06-Agent设计.md` 和 `docs/02-技术选型.md` 为准。
- 项目文件接口当前依赖 MinIO 相关能力；本地联调时确认 `deploy/docker-compose.yml` 中对应服务是否已启动。

## Git 与文档

- 仓库采用 Monorepo + `main` 主干 + `feature/*` 任务分支；目录区分模块，分支区分任务。
- 提交信息建议使用 Conventional Commits，例如 `feat(auth): 完成登录接口与前端联调`。
- 涉及接口规范时同步更新 `docs/05-接口规范.md`；涉及 Agent 设计时同步更新 `docs/06-Agent设计.md`；涉及中间件和本地启动时同步更新 `deploy/README.md`。
- 不要提交 `node_modules/`、`.venv/`、`__pycache__/`、本地 `.env` 或生成数据文件。
