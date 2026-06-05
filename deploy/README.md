# 本地 Docker 中间件

本目录用于管理 PM-Agent 本地开发所需中间件。第 1 阶段只启用 MySQL 8，前端和后端均在本机运行。

## 启动步骤

### 1. 准备环境变量

```bash
cp deploy/.env.example deploy/.env
```

### 2. 启动 MySQL

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

### 3. 查看状态

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

### 4. 验证连接

```bash
docker exec -it pm-agent-mysql mysql -upm_agent -ppm_agent_dev pm_agent
```

进入 MySQL 后可执行：

```sql
SHOW DATABASES;
SELECT DATABASE();
```

## 停止服务

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

## 重置本地数据

仅在确认不需要保留本地数据时执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```

## 职责边界

- Docker 负责启动 MySQL 服务；
- Flyway 负责后端业务表结构和初始化演示数据；
- 不建议把业务建表 SQL 放入 `deploy/mysql/init/`。
