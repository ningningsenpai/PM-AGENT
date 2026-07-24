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
└── agents、llm、memory、normalization、project、rag 等既有 Agent 能力
```

业务模块均按 `api.py / schemas.py / models.py / domain.py / repository.py / service.py / errors.py` 拆分。API 不直接访问基础设施，Repository 不跨模块调用，MinIO 与模型调用不放在数据库事务内。

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
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
```

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

`tests/test_Qwen_output.py` 是需要真实模型和人工观察输出的实验脚本，不属于默认自动化测试集合。

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
