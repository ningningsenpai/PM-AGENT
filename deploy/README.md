# 本地中间件

PM-Agent 在线运行时使用 MySQL、Redis 和 MinIO。RabbitMQ 不在本次 Python 单体迁移链路中，Qdrant 仅保留为显式启用的 RAG 实验 Profile。

## 启动

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql redis minio
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

服务默认只绑定到 `127.0.0.1`：

| 服务 | 默认地址 | 用途 |
|---|---|---|
| MySQL | `127.0.0.1:3306` | 业务数据 |
| Redis | `127.0.0.1:6379` | 登录会话与两分钟幂等结果 |
| MinIO API | `127.0.0.1:9000` | 项目文件和上下文快照 |
| MinIO Console | `127.0.0.1:9001` | 本地对象管理 |

如需单独验证未纳入在线基线的 RAG 实验：

```bash
docker compose --profile rag --env-file deploy/.env -f deploy/docker-compose.yml up -d qdrant
```

## 后端开发启动

在 `agent-service/` 目录中，普通开发使用 `python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000`，热重载只监听 `app/`。测试脚本、调用记录和测试源文件不纳入监听范围。

PyCharm 断点调试使用项目提供的 `agent-service 调试` 运行配置，以单进程启动并关闭热重载；`agent-service 热重载` 配置用于普通 Run。切换配置前停止已有后端进程，修改 `.env` 后手动重启。详细步骤见 `agent-service/README.md` 的“启动后端”。

文件详情与项目规范的模型输出额度由 `agent-service/.env` 的 `PM_AGENT_FILE_DETAIL_MAX_OUTPUT_TOKENS` 配置，默认 `16384`，直接传入 `max_tokens`。它与普通聊天的 `DEEPSEEK_RESERVED_OUTPUT_TOKENS` 输出预留、`DEEPSEEK_CONTEXT_WINDOW_TOKENS` 上下文预算分别配置。JSON 生成显式关闭 DeepSeek 思考模式，已知 V4 模型超过 `384000` 时会在本地拒绝请求。HTTP 错误查看 `模型 HTTP 请求失败` 日志；HTTP `200` 后的截断或字段问题查看 `结构化模型生成完成` 和 `结构化模型输出校验失败` 日志。修改环境变量后重启后端，详细说明见 `agent-service/README.md` 的“文件解析链路”。

## 数据库迁移

容器只负责创建空数据库，不在 `deploy/mysql/init/` 放业务建表脚本。唯一 Schema 所有者是 Python Alembic：

```bash
cd agent-service
python -m alembic upgrade head
```

本次迁移不导入历史业务数据。开发库如果还包含旧 Flyway 结构，应先确认数据可丢弃，再重建空库并执行 Alembic。

### 移除旧分析版本字段

已有项目数据升级到不含 `analysis_version` 的上下文协议时，需要维护窗口。先停止 Agent 服务和文件写入，在新代码目录执行只读检查和对象迁移，确认成功后再删除数据库字段：

```bash
cd agent-service
python -m app.maintenance.remove_analysis_version --dry-run
python -m app.maintenance.remove_analysis_version --apply
python -m alembic upgrade head
```

维护命令会迁移有效详情、更新项目规范引用、重建 `index.json` 并清理旧详情对象。缺失或格式错误的旧详情会失效，后续由普通文件分析重新生成。命令失败时不得继续执行 Alembic；修复 MinIO 或数据库问题后可重复运行。

## 到期项目定时清理

项目惰性删除后保留三十天。外部定时器通过以下一次性命令清理已经超过 `purge_after` 的项目：

```bash
cd agent-service
python -m app.maintenance.purge_disabled_projects
```

命令逐个项目清空 MinIO 前缀，确认无剩余对象后再物理删除 MySQL 项目记录；项目文件记录由外键级联删除。单个项目失败不会阻止后续项目，失败记录在下一次计划执行时会再次被扫描。外部定时器应禁止任务重叠执行，并关闭失败后的立即重试，只保留下一次计划执行。

## 停止与重置

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

以下操作会删除 MySQL、Redis、MinIO 等数据卷，只能在确认无需保留数据后执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```
