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

## 停止与重置

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

以下操作会删除 MySQL、Redis、MinIO 等数据卷，只能在确认无需保留数据后执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```
