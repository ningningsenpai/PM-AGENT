# HTTP 请求客户端

本目录按照在线业务模块分层，用于通过 JetBrains HTTP Client 手工调用 FastAPI 接口。请求直接经过 API、认证和真实中间件，不属于 `tests/unit/` 单元测试。

```text
test_client/
├── http-client.env.json
└── modules/
    ├── auth/auth.http
    ├── user/user.http
    ├── project/project.http
    └── project_file/
        ├── management/file_management.http
        └── analysis/file_analysis.http
```

## 使用前提

1. 启动 MySQL、Redis 和 MinIO。
2. 在 `agent-service/` 中执行 `python -m alembic upgrade head`。
3. 启动服务：`uvicorn app.main:app --reload --port 8000`。
4. 在 HTTP Client 中选择 `dev` 环境。
5. 每次完整执行前修改 `http-client.env.json` 中的 `runId`，避免项目名、文件路径和幂等键与上一次调用冲突。

## 推荐执行顺序

1. 执行 `auth/auth.http` 的注册或登录请求，脚本会保存 `accessToken`。
2. 按需执行 `user/user.http`。
3. 执行 `project/project.http` 的创建项目请求，脚本会保存 `projectId`。
4. 执行 `project_file/management/file_management.http` 的上传、查询、覆盖和改名请求。
5. 执行 `project_file/analysis/file_analysis.http` 的解析请求。
6. 最后依次执行删除文件、删除项目和注销请求。

`accessToken`、`projectId`、`fileId` 和 `fileLockVersion` 由响应脚本保存为 HTTP Client 全局变量。若调用顺序被打断，可重新执行产生该变量的请求；若变量指向旧数据，可在 HTTP Client 的全局变量界面清除后重新开始。

标注“最后执行”或“可选副作用”的请求会修改或删除数据，不应在主流程中提前运行。
