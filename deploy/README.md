# 本地 Docker 中间件

本目录用于管理 PM-Agent 本地开发所需的中间件，目标是用 Docker 统一启动数据库与基础设施，保持后端和前端在本机运行（便于断点调试和热更新）。

## 阶段策略

PM-Agent 严格遵守“中间件按阶段引入，不一次性堆叠”的原则。Docker Compose 文件中只启用当前阶段必需的服务。

| 阶段 | 中间件 | Compose 状态 | 用途 |
|---|---|---|---|
| 第 1 阶段 | MySQL 8 | 默认启用 | 业务数据库 |
| 第 2 阶段 | Redis 7 | 后续加入并启用 | Sa-Token 会话、缓存、限流、幂等集中校验 |
| 第 5 阶段 | RabbitMQ | 后续加入并启用 | 异步任务、风险扫描、通知 |
| 第 6 阶段 | MinIO | 后续加入并启用 | 文档、附件、报告文件 |
| 小型 RAG 测试 | Qdrant | 可随本地 Compose 启动 | 向量检索链路验证 |

后端 Spring Boot 工程和前端 Vite 工程在第 1 阶段都不进入容器，便于本地开发。容器化打包属于后期部署阶段的话题，不在 `deploy/` 当前职责内。

## 目录结构

```text
deploy/
├── docker-compose.yml   # 本地中间件编排
├── .env.example         # Docker Compose 环境变量示例
├── mysql/
│   ├── conf.d/
│   │   └── my.cnf       # MySQL 本地配置
│   └── init/            # 容器级初始化目录，默认不放业务建表脚本
└── README.md            # 本说明
```

业务表结构由后端 Flyway 管理，不放到 MySQL 容器初始化目录。

## 启动步骤

### 1. 准备环境变量

```bash
cp deploy/.env.example deploy/.env
```

如需修改默认账号、密码或端口，可编辑 `deploy/.env`。

### 2. 启动 MySQL 和 Qdrant

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

如当前只需要业务数据库，也可以单独启动 MySQL：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql
```

### 3. 查看容器状态

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

### 4. 查看 MySQL 日志

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs mysql
```

### 5. 查看 Qdrant 日志

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs qdrant
```

### 6. 验证 MySQL 连接

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec mysql mysql -upm_agent -ppm_agent_dev pm_agent
```

进入 MySQL 后可执行：

```sql
SHOW DATABASES;
SELECT DATABASE();
```

### 7. 验证 Qdrant 连接

```bash
curl http://localhost:6333/healthz
```

Qdrant Dashboard 默认访问地址：

```text
http://localhost:6333/dashboard
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

`down -v` 会删除 MySQL 数据卷，执行前务必确认本地无重要数据。

## 后端连接配置

后端本机运行时通过本地端口连接 MySQL 容器：

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/pm_agent?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true
    username: pm_agent
    password: pm_agent_dev
  flyway:
    enabled: true
    locations: classpath:db/migration
```

## 职责边界

| 职责 | Docker / MySQL 容器 | Flyway |
|---|---|---|
| 启动 MySQL 服务 | 是 | 否 |
| 创建数据库实例 | 是 | 否 |
| 管理业务表结构 | 否 | 是 |
| 插入演示业务数据 | 不建议 | 是 |
| 记录数据库版本 | 否 | 是 |
| 支持后续表结构演进 | 否 | 是 |

结论：Docker 管“数据库服务能不能起来”，Flyway 管“业务表结构是什么版本”。

## 常见问题

### 1. 为什么第 1 阶段不启动 Redis、RabbitMQ 等？

第 1 阶段只要求登录、项目和任务最小闭环。Sa-Token JWT 可先以单体应用配置运行，幂等先完成请求头必填校验。Redis、RabbitMQ、MinIO、向量库按阶段加入，避免第 1 阶段中间件过多。

### 2. 为什么后端和前端不放进 Docker？

第 1 阶段处于高频开发期，后端需要断点调试，前端需要热更新，本机运行更高效。等进入部署阶段，再考虑后端、前端和 Python Agent 服务的容器化打包。

### 3. 为什么业务建表不放到 MySQL 初始化目录？

MySQL 初始化目录只在容器首次启动时执行一次脚本，不适合长期版本演进。业务表结构需要可追踪、可升级、可回滚，因此交给 Flyway 管理更合适。

## 验收标准

- `docker compose up -d` 可启动 MySQL 8；
- 健康检查通过；
- 后端本机可以连接 MySQL 容器；
- 后端启动后 Flyway 能自动执行迁移脚本；
- 第 1 阶段只启动 MySQL，不提前启动 Redis、RabbitMQ、MinIO、向量库。
