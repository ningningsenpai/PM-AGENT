# PM-Agent

PM-Agent 是面向项目经理与研发团队的智能项目管理平台。当前在线架构已经收敛为：

```text
Vue 3 → FastAPI 模块化单体 → MySQL / Redis / MinIO / LLM
```

## 当前能力

- 邮箱注册、登录、注销和当前用户资料；
- 项目创建、列表、详情与删除；
- 项目文件上传、覆盖、移动、列表、读取地址与删除；
- 进程内文件解析、文件详情投影和 `system/index.json` 重建；
- Agent JSON/SSE 对话与既有模型适配能力。

Python 是业务数据唯一写入者，Alembic 是数据库结构唯一迁移工具。Agent 工具只能调用业务模块 Service，不能直接获取 SQLAlchemy Session 或执行模型生成的 SQL。

## 目录

```text
PM-AGENT/
├── frontend/         # Vue 3 + TypeScript + Naive UI
├── agent-service/    # FastAPI 模块化单体后端与既有 Agent 能力
├── archive/          # 本地留档资产，已通过 .gitignore 忽略
├── deploy/           # MySQL、Redis、MinIO 本地编排
└── docs/             # 产品、架构、接口与验收文档
```

`scripts/`、`eval/`、`training/`、`normalization_demo/`、`examples/` 和 `resources/` 已迁移至本地 `archive/agent-service-deferred/`，等待主业务完成后再优化。该目录不纳入 Git；`agent-service/project_test/` 仍是独立实验资产。

## 本地启动

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql redis minio

cd agent-service
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

另开终端启动前端：

```bash
cd frontend
pnpm install
pnpm dev
```

访问地址：

- 前端：`http://localhost:5173`
- FastAPI 健康检查：`http://localhost:8000/internal/health`
- OpenAPI：`http://localhost:8000/docs`
- MinIO 控制台：`http://localhost:9001`

## 验证

```bash
cd agent-service
python -m pytest
python -m alembic upgrade head --sql

cd ../frontend
pnpm typecheck
pnpm build
```

关键设计以 [技术选型](./docs/02-技术选型.md)、[接口规范](./docs/05-接口规范.md)、[Agent 设计](./docs/06-Agent设计.md) 和 [Python 迁移说明](./docs/21-Python单体后端迁移说明.md) 为准。
