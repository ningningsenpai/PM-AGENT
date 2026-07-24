# Agent 专项历史文档

本目录保留记忆、事件图谱、接入层和演示项目等专项设计资料，其中部分内容形成于 Java 与 Python 分服务阶段。

当前在线运行架构、数据所有权和工具边界统一以以下文档为准：

- [Python 单体后端迁移说明](../../docs/21-Python单体后端迁移说明.md)
- [技术选型](../../docs/02-技术选型.md)
- [接口规范](../../docs/05-接口规范.md)
- [Agent 设计](../../docs/06-Agent设计.md)

专项文档中出现的 Java 工具 API、Java 业务数据库、Spring Boot、Sa-Token、MyBatis Plus 或 Flyway 描述只代表历史方案。继续实现相关能力时，必须改为调用 `app/modules/` 中的公开 Service，不得恢复跨服务业务自调用，也不得让 Agent 直接取得 SQLAlchemy Session。
