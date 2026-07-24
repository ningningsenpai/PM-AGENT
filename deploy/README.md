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

## 停止与重置

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

以下操作会删除 MySQL、Redis、MinIO 等数据卷，只能在确认无需保留数据后执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```
