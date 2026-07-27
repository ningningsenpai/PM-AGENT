# PM-Agent Python 单体后端

`agent-service/` 现在同时承载认证、用户、项目、项目文件与 Agent 在线能力。运行时链路为：

```text
Vue 3 → FastAPI → MySQL / Redis / MinIO / LLM
```

Java 不再是运行依赖。业务表只由 SQLAlchemy 访问，Schema 只由 Alembic 管理；Agent 工具必须通过 `app/modules/` 中的公开 Service 使用业务能力。

## 模块边界

```text
app/
├── api/v1/                 # 路由聚合
├── core/                   # 配置、响应、异常、认证、Trace、幂等
├── infrastructure/         # MySQL、Redis、MinIO 适配
├── modules/
│   ├── auth/
│   ├── user/
│   ├── project/
│   └── project_file/
│       ├── api.py、domain.py、models.py、repository.py
│       ├── management/     # 源文件生命周期与 MinIO 文件管理
│       └── analysis/       # 文件分析编排与派生结果写入
└── agents、llm、memory、normalization、project、rag 等既有 Agent 能力
```

普通业务模块按 `api.py / schemas.py / models.py / domain.py / repository.py / service.py / errors.py` 拆分。`project_file` 在共享 ORM、状态枚举和 Repository 的基础上进一步拆成两个子包：`management` 负责上传、覆盖、改名、删除、列表、预签名地址和源文件状态机；`analysis` 只读取源文件、调用分析器、写入 `system/file_details/*.json`、更新分析投影并触发索引重建。两个子包不得互相依赖，通过根包公开各自的 Service。

API 不直接访问基础设施，Repository 不跨模块调用，MinIO 与模型调用不放在数据库事务内。MinIO 权限也按职责收敛：文件管理服务可以管理用户源文件，分析服务只能读取源文件并写入分析派生物，不得改名或删除用户源文件。

## 本地启动

先启动当前在线链路所需中间件：

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql redis minio
```

安装依赖并执行数据库基线：

```bash
cd agent-service
python -m venv .venv
source .venv/Scripts/activate
python scripts/install_dependencies.py
cp .env.example .env
python -m alembic upgrade head
```

安装脚本始终使用执行它的 `sys.executable`，因此依赖会安装到当前激活的 Python 环境。依赖清单统一维护在 `pyproject.toml`，脚本不会另行维护一份包版本列表。

启动后端：

```bash
uvicorn app.main:app --reload --port 8000
```

前端 Vite 已将 `/api` 代理到 `http://localhost:8000`。

## 验证

```bash
python -m pytest
python -m alembic upgrade head --sql
```

## 文件解析链路

`POST /api/v1/projects/{projectId}/files/parse/init` 在同一 Python 进程内完成：

1. 从 MySQL 查询尚未解析的活动文件；
2. 使用对象键通过 MinIO SDK 读取内容；
3. 调用既有本地解析器和模型适配器；
4. 通过 Pydantic 校验结构和文件身份字段；
5. 写入 `system/file_details/*.json`；
6. 条件更新分析投影与解析次数；
7. 从数据库全量重建 `system/index.json`。

旧的 `/api/v1/project-files/analyze` 已移除。`index.json` 只是可重建快照，不是业务权威数据源。
