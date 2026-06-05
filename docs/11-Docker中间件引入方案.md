# Docker 中间件引入方案

## 1. 背景

PM-Agent 采用 Java 后端、Vue 前端、Python Agent 服务和多个中间件协同的架构。为降低本地安装成本，并保持后续开发环境可复现，项目决定使用 Docker 容器承载中间件。

第 1 阶段仅启用 MySQL 8；Redis、RabbitMQ、MinIO、向量库等中间件按阶段逐步加入 Docker Compose，不提前启动，避免增加本地运行负担。

---

## 2. 目标

1. 使用 Docker 统一管理本地中间件；
2. 第 1 阶段只启动 MySQL，支撑用户、项目、任务基础闭环；
3. 保持后端和前端本机运行，便于断点调试和热更新；
4. 为后续 Redis、RabbitMQ、MinIO、向量库预留清晰扩展路径；
5. 明确目录、配置、启动、停止、验证和数据清理步骤。

---

## 3. 范围

### 3.1 本期范围

| 内容 | 是否启用 | 说明 |
|---|---|---|
| Docker Compose | 是 | 管理本地中间件 |
| MySQL 8 | 是 | 第 1 阶段业务数据库 |
| 后端 Spring Boot 容器化 | 否 | 本机运行，便于调试 |
| 前端 Vite 容器化 | 否 | 本机运行，便于热更新 |
| Redis | 否 | 第 2 阶段再启用 |
| RabbitMQ | 否 | 第 5 阶段再启用 |
| MinIO | 否 | 第 6 阶段再启用 |
| Qdrant / pgvector | 否 | 第 6 阶段评估后再启用 |

### 3.2 不做范围

- 不在第 1 阶段做全栈容器化；
- 不在第 1 阶段启动 Redis；
- 不在第 1 阶段启动 RabbitMQ；
- 不在第 1 阶段启动 MinIO 或向量库；
- 不把生产部署方案和本地开发方案混在一起。

---

## 4. 推荐目录结构

```text
PM-AGENT/
├── deploy/
│   ├── docker-compose.yml              # 本地中间件编排
│   ├── .env.example                    # Docker Compose 环境变量示例
│   ├── mysql/
│   │   ├── conf.d/
│   │   │   └── my.cnf                  # MySQL 本地配置
│   │   └── init/                       # 可选：容器级初始化脚本，默认不放业务建表脚本
│   └── README.md                       # 本地中间件启动说明
├── backend/
│   └── ...                             # 后端工程，使用 Flyway 管理业务建表
└── frontend/
    └── ...                             # 前端工程
```

说明：

- `deploy/` 只负责中间件容器；
- 业务表结构由后端 Flyway 管理，不建议放到 MySQL 容器初始化目录；
- MySQL 容器只负责创建数据库实例和提供连接能力；
- 后端启动时通过 Flyway 执行 `V1__...sql` 等迁移脚本。

---

## 5. 第 1 阶段 MySQL 容器方案

### 5.1 容器内容

| 项目 | 建议值 |
|---|---|
| 镜像 | `mysql:8.0` |
| 容器名 | `pm-agent-mysql` |
| 数据库名 | `pm_agent` |
| 默认端口 | `3306:3306` |
| 字符集 | `utf8mb4` |
| 排序规则 | `utf8mb4_0900_ai_ci` |
| 数据卷 | `pm-agent-mysql-data` |
| 健康检查 | 使用 `mysqladmin ping` |

### 5.2 环境变量示例

建议 `deploy/.env.example` 包含：

```dotenv
MYSQL_ROOT_PASSWORD=pm_agent_root
MYSQL_DATABASE=pm_agent
MYSQL_USER=pm_agent
MYSQL_PASSWORD=pm_agent_dev
MYSQL_PORT=3306
```

实际运行时复制为：

```bash
cp deploy/.env.example deploy/.env
```

然后按需修改密码。

---

## 6. Docker Compose 推荐内容

第 1 阶段建议 `deploy/docker-compose.yml` 只启用 MySQL：

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: pm-agent-mysql
    restart: unless-stopped
    ports:
      - "${MYSQL_PORT:-3306}:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-pm_agent_root}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-pm_agent}
      MYSQL_USER: ${MYSQL_USER:-pm_agent}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-pm_agent_dev}
      TZ: Asia/Shanghai
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_0900_ai_ci
      - --default-time-zone=+08:00
    volumes:
      - pm-agent-mysql-data:/var/lib/mysql
      - ./mysql/conf.d:/etc/mysql/conf.d:ro
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 10

volumes:
  pm-agent-mysql-data:
```

---

## 7. 启动、停止与验证步骤

### 7.1 准备环境变量

```bash
cp deploy/.env.example deploy/.env
```

### 7.2 启动中间件

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

### 7.3 查看容器状态

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

### 7.4 查看 MySQL 日志

```bash
docker logs pm-agent-mysql
```

### 7.5 验证 MySQL 连接

```bash
docker exec -it pm-agent-mysql mysql -upm_agent -ppm_agent_dev pm_agent
```

进入 MySQL 后可执行：

```sql
SHOW DATABASES;
SELECT DATABASE();
```

### 7.6 停止中间件

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

### 7.7 清理数据卷

仅在需要重置本地数据库时执行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```

注意：`down -v` 会删除 MySQL 本地数据卷，执行前需要确认没有重要数据。

---

## 8. 后端连接配置

后端本机运行时，建议开发环境连接本地 Docker MySQL：

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

说明：

- MySQL 容器只提供数据库服务；
- Flyway 在后端启动时自动创建业务表；
- 第 1 阶段建表脚本应放在后端工程 `src/main/resources/db/migration/` 下。

---

## 9. Flyway 与 Docker 的职责边界

| 职责 | Docker / MySQL 容器 | Flyway |
|---|---|---|
| 启动 MySQL 服务 | 是 | 否 |
| 创建数据库实例 | 是 | 否 |
| 管理业务表结构 | 否 | 是 |
| 插入演示业务数据 | 不建议 | 是 |
| 记录数据库版本 | 否 | 是 |
| 支持后续表结构演进 | 否 | 是 |

结论：

- Docker 管“数据库服务能不能起来”；
- Flyway 管“业务表结构是什么版本”。

---

## 10. 后续中间件扩展步骤

### 10.1 第 2 阶段加入 Redis

用途：

- Sa-Token 会话；
- 接口缓存；
- 限流；
- 幂等缓存从 Caffeine 切换到 Redis。

引入步骤：

1. 在 `docker-compose.yml` 新增 Redis service；
2. 在 `deploy/.env.example` 新增 Redis 端口和密码；
3. 后端新增 Redis 依赖和连接配置；
4. Sa-Token 存储从内存切换到 Redis；
5. 幂等拦截器缓存从 Caffeine 切换到 Redis；
6. 更新 `docs/02-技术选型.md`、`docs/05-接口规范.md` 和阶段总结。

---

### 10.2 第 5 阶段加入 RabbitMQ

用途：

- 异步任务；
- 风险扫描；
- 通知事件；
- Agent 后台任务。

引入步骤：

1. 在 `docker-compose.yml` 新增 RabbitMQ service；
2. 启用管理控制台端口；
3. 后端新增 RabbitMQ 配置；
4. 设计交换机、队列、路由键；
5. 将风险扫描、通知等异步流程接入 MQ；
6. 补充运维和失败重试说明。

---

### 10.3 第 6 阶段加入 MinIO

用途：

- 文档上传；
- 附件存储；
- 报告文件存储；
- RAG 文档原文保存。

引入步骤：

1. 在 `docker-compose.yml` 新增 MinIO service；
2. 配置 access key、secret key、bucket；
3. 后端新增文件服务适配层；
4. 前端新增文档上传页面；
5. 明确文件访问权限和清理策略。

---

### 10.4 第 6 阶段评估向量库

候选方案：

| 方案 | 说明 |
|---|---|
| pgvector | 如果未来切 PostgreSQL 或引入单独 PostgreSQL，可减少中间件数量 |
| Qdrant | 专用向量库，检索能力更强，适合文档量增长后使用 |

引入步骤：

1. 根据文档规模和检索需求决定 pgvector 或 Qdrant；
2. 在 Docker Compose 中加入对应服务；
3. 设计文档切片、向量化、检索和引用来源表结构；
4. Python Agent 服务接入向量检索；
5. 更新 `docs/06-Agent设计.md` 和 `docs/07-成本控制.md`。

---

## 11. 常见问题

### 11.1 为什么第 1 阶段不启动 Redis？

第 1 阶段只要求登录、项目和任务最小闭环。Sa-Token 可以先使用内存模式，幂等键可以先用本地 Caffeine。Redis 第 2 阶段再引入，避免第 1 阶段中间件过多。

### 11.2 为什么后端和前端不放进 Docker？

第 1 阶段处于高频开发期，后端需要断点调试，前端需要热更新。本机运行更高效。等进入部署阶段，再考虑 Java、Python 和前端静态资源容器化。

### 11.3 为什么业务建表不放到 MySQL 初始化目录？

MySQL 初始化目录只适合容器首次启动时执行一次脚本，不适合长期版本演进。业务表结构需要可追踪、可升级、可回滚，因此交给 Flyway 管理更合适。

---

## 12. 验收标准

- `deploy/` 目录创建完成；
- `deploy/docker-compose.yml` 可以启动 MySQL 8；
- `deploy/.env.example` 提供必要环境变量；
- MySQL 容器健康检查通过；
- 后端本机可以连接 MySQL 容器；
- 后端启动后 Flyway 能自动执行迁移脚本；
- 第 1 阶段只启动 MySQL，不提前启动 Redis、RabbitMQ、MinIO、向量库。

---

## 13. 待确认问题

暂无。后续进入第 2、5、6 阶段时，再分别确认 Redis、RabbitMQ、MinIO 和向量库的具体配置。
