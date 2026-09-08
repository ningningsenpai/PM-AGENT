# HTTP 请求客户端

本目录按照在线业务模块分层，用于通过 JetBrains HTTP Client 手工调用 FastAPI 接口。请求直接经过 API、认证和真实中间件，不属于 `tests/unit/` 单元测试。

```text
test_client/
├── http-client.env.example.json  # 仓库中的安全模板
├── http-client.env.json          # 本地配置，已加入 Git 忽略
└── modules/
    ├── auth/auth.http
    ├── user/user.http
    ├── project/project.http
    └── project_file/
        ├── management/file_management.http
        ├── analysis/file_analysis.http
        └── sync/file_sync.http
```

## 使用前提

1. 启动 MySQL、Redis 和 MinIO。
2. 在 `agent-service/` 中执行 `python -m alembic upgrade head`。
3. 启动服务：`python -m uvicorn app.main:app --reload --reload-dir app --port 8000`；在 PyCharm 中设置断点时使用 `agent-service 调试` 配置。
4. 首次使用时，将 `http-client.env.example.json` 复制为同目录的 `http-client.env.json`，只在本地配置中填写账号、密码、登录令牌、项目 ID 和文件路径；已有本地配置时保留原文件。认证和用户请求使用 `dev` 环境，项目请求可使用 `project` 环境，项目文件目录下的请求统一使用 `project_file` 环境。
5. 每轮项目文件测试前修改 `http-client.env.json` 中的 `project_file.runId`，避免文件路径和幂等键与上一次调用冲突；同轮重复上传验证时保持不变。

## 项目文件环境

`project_file` 环境独立配置该目录所需的变量，请求不包含响应脚本，响应中的 ID 和锁版本需手动回填。

| 变量 | 用途与填写方式 |
|---|---|
| `baseUrl` | FastAPI 服务地址，默认 `http://localhost:8000` |
| `accessToken` | 初始为空，填写登录响应中的 `data.accessToken` |
| `projectId` | 初始为空，执行前填写当前登录用户拥有的项目 ID |
| `runId` | 本轮测试标识，用于生成文件名、相对路径及上传、覆盖幂等键 |
| `fileId` | 初始为空，填写上传响应中的 `data.fileId`，也可从文件列表的 `id` 获取 |
| `fileLockVersion` | 填写目标文件的最新 `lockVersion`；初始值 `0` 仅为占位，不能直接用于覆盖、改名或删除 |
| `businessCode` | 文件列表过滤条件，默认 `project`，也支持 `user` |
| `sourceMtimeMs` | 上传文件的源修改时间，单位为毫秒 |
| `overwriteSourceMtimeMs`、`pathSourceMtimeMs` | 覆盖内容、修改路径时提交的源修改时间，单位为毫秒 |
| `forceAnalysis` | 默认 `false`，仅分析待处理文件；`true` 重新分析全部有效文件 |
| `syncSnapshotComplete` | 默认 `false`；仅在 `items` 包含完整项目清单时设为 `true` |
| `syncRelativePath`、`syncSizeBytes`、`syncSourceMtimeMs` | 同步清单中文件的相对路径、实际字节数和源修改时间 |
| `syncContentHash`、`syncContentType` | 同步清单中文件的完整 SHA-256 和 MIME 类型；环境中的值是示例，按本地文件实际内容填写 |

项目 ID 和文件 ID 使用字符串保存；锁版本、字节数、时间戳使用数值，分析开关和完整快照标志使用布尔值。

模板中的账号名称和邮箱仅作示例，密码与令牌留空。真实配置只保存在被忽略的 `http-client.env.json`，不要回填到示例文件；创建项目请求通过 `projectName` 变量取值，不在 `.http` 文件中写死本地项目名称。

## 推荐执行顺序

1. 执行 `auth/auth.http` 的注册或登录请求，将 `data.accessToken` 手动填入后续请求所选环境的 `accessToken`。
2. 按需执行 `user/user.http`。
3. 创建项目或查询已有项目，将项目 `id` 填入 `project_file.projectId`，然后切换到 `project_file` 环境。
4. 执行文件上传请求，确认 `data.success=true` 和 `data.uploadStatus=success` 后回填 `fileId`。需要验证重复提交时，紧接着执行相同幂等键的重复上传请求。
5. 查询文件列表，找到目标文件并回填 `fileLockVersion`，再按需执行覆盖和路径修改请求。上传响应不包含锁版本，覆盖和路径修改成功后需要从各自响应的 `data.lockVersion` 再次回填。
6. 按需执行 `project_file/sync/file_sync.http`，查看 `unchanged`、`modified`、`moved`、`added`、`deleted`、`rejected` 和 `ambiguous`。该接口只生成差异计划，不执行文件变更。
7. 执行 `project_file/analysis/file_analysis.http` 的分析请求。业务码为 `200` 时仍需检查 `data.status`、`failureCount`、`failures`、`specificationStatus` 和 `indexStatus`；文件列表中的 `parseAttempts` 只表示尝试次数。
8. 完成验证后，查询文件列表并回填最新锁版本，再执行删除文件；删除成功后清空 `project_file.fileId`。删除项目和注销请求切换回对应环境执行。

若调用顺序被打断，重新查询目标文件并回填 `fileId` 和 `fileLockVersion`。使用过旧版请求脚本时，可清理遗留的同名 HTTP Client 全局变量，统一在所选环境中维护测试数据。

标注“最后执行”或“可选副作用”的请求会修改或删除数据，不应在主流程中提前运行。
