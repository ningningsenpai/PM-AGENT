# 项目文件流程调试

本目录用 Python 模拟项目文件首次上传和后续更新时前端承担的工作：扫描本地目录、生成同步清单、逐个上传新增文件、更新已有文件的内容或路径、删除规划中的远端文件、触发批量解析以及查询文件列表。使用现有 `httpx` 依赖，通过真实 HTTP 调用 `project_file` 模块接口。

脚本用于观察数据流转，不包含结果断言、预期响应比对或通过率统计。数据库写入、原始文件存储、模型解析以及解析产物写入 MinIO 均由后端执行。

## 配置

复用 `agent-service/test_client/http-client.env.json` 中的 `project_file` 环境。脚本默认根据自身位置找到该文件，与启动时的工作目录无关。

| 配置项 | 用途 |
|---|---|
| `baseUrl` | 已启动的 FastAPI 服务地址，例如 `http://localhost:8000` |
| `accessToken` | 有效登录令牌；对应用户需拥有目标项目 |
| `projectId` | 已创建项目的 ID |
| `runId` | 本轮记录标识，同一轮分阶段调用保持不变，新一轮更换标识 |
| `sourceDir` | 实际测试文件夹，例如 `D:/Code/ning/PM-AGENT/agent-service/project_test/docs` |
| `forceAnalysis` | 默认 `false`，传给解析接口的 `force` 查询参数 |

`runId` 支持 1 至 80 位字母、数字、下划线和短横线，以字母或数字开头。`sourceDir` 也可填写相对于环境文件目录的路径。

文件的修改时间、大小和 SHA-256 从实际文件计算；不使用 HTTP 请求示例中的 `sourceMtimeMs`、`syncRelativePath` 等手工变量，也不要求回填 `fileId` 或 `fileLockVersion`。目录扫描生成完整清单，固定提交 `snapshotComplete=true`，不使用单文件 HTTP 示例中的 `syncSnapshotComplete`。

扫描时参考前端的忽略目录、文件后缀、大小及 MIME 筛选规则，拒绝项仅记录元数据和原因。MIME 类型由扩展名推断，其中 `.ts`、`.tsx` 明确按文本处理，避免系统把 TypeScript 源码识别成视频流。

运行前需启动 FastAPI、MySQL、Redis 和 MinIO，并在后端配置、开启文件语义分析模型。测试文件夹内的样例系统无需启动，脚本只读取其文件。

后端断点调试使用 PyCharm 的 `agent-service 调试` 配置。普通开发可在 `agent-service/` 下运行 `python -m uvicorn app.main:app --reload --reload-dir app --port 8000`，只监听后端源码，避免修改本目录脚本时触发重载。两种启动方式详见后端 README 的“启动后端”。

## 分阶段执行

在 PowerShell 中设置脚本与已有虚拟环境的路径：

```powershell
$flowPython = 'D:/Code/ning/PM-AGENT/agent-service/.venv/Scripts/python.exe'
$flowScript = 'D:/Code/ning/PM-AGENT/agent-service/tests/project_file_flow/run.py'

& $flowPython $flowScript --help
```

| 阶段 | 行为 | 接口，省略 `/api/v1/projects/{projectId}/files` 前缀 |
|---|---|---|
| `plan` | 扫描目录、计算元数据、保存清单并请求同步规划 | `POST /sync/plan` |
| `upload` | 读取本轮保存的规划，对 `data.added` 逐个上传 | 每个文件调用一次 `POST /` |
| `update` | 读取本轮保存的规划，依次处理 `data.modified`、`data.moved`、`data.deleted` | 内容覆盖：`PUT /{remoteFileId}/content`；路径变更：`PATCH /{remoteFileId}/path`；删除：`DELETE /{remoteFileId}?lockVersion=…` |
| `parse` | 触发项目批量解析，等待后端完成解析与产物保存 | `POST /parse/init?force=…` |
| `files` | 查询文件列表和状态 | `GET /?businessCode=project` |
| `all` | 顺序执行 `plan → upload → update → parse → files` | 上述全部阶段 |

```powershell
# 扫描文件夹并生成同步计划。
& $flowPython $flowScript plan

# 查看本地清单和规划响应，再上传新增项。
& $flowPython $flowScript upload

# 根据同一轮规划覆盖内容、更新路径并删除远端删除项。
& $flowPython $flowScript update

# 查看上传和更新后的状态。
& $flowPython $flowScript files

# 开始解析；可以在后端设置断点观察读取、模型调用和存储过程。
& $flowPython $flowScript parse

# 查看解析后的状态。
& $flowPython $flowScript files
```

完整执行或指定另一份环境文件：

```powershell
& $flowPython $flowScript all
& $flowPython $flowScript plan --env-file 'D:/Code/ning/PM-AGENT/agent-service/test_client/http-client.env.json'
```

`upload` 仅执行 `added`，`update` 执行 `modified`、`moved` 和 `deleted`；`unchanged`、`rejected` 和 `ambiguous` 保留在规划响应中，不自动处理。对同一项目再次执行 `plan`，已有且相同的文件通常进入 `unchanged`，因此上传、更新都可能无需发送请求。更换 `runId` 只建立新的本地记录分组，不会改变文件的项目相对路径。

各阶段不会自动补做前置步骤。`upload` 和 `update` 需要本轮已有的 `manifest.json` 和 `plan.response.json`；项目、服务地址或目录变化时重新执行 `plan`。规划后本地文件有变化时会留下跳过记录，重新规划后再上传或更新。

## 更新已有文件

修改本地文件内容，或者移动、重命名、删除文件后，执行：

```powershell
& $flowPython $flowScript plan
& $flowPython $flowScript update
& $flowPython $flowScript files
& $flowPython $flowScript parse
```

| 规划分类 | 更新请求内容 |
|---|---|
| `modified` | 从规划读取 `remoteFileId` 和 `lockVersion`，以 multipart 表单发送 `file`、`sourceMtimeMs`、`lockVersion`，携带 `X-Idempotency-Key` |
| `moved` | 从规划读取 `remoteFileId` 和 `lockVersion`，以 JSON 发送新的 `relativePath`、`sourceMtimeMs`、`lockVersion`，不上传文件正文 |
| `deleted` | 从规划读取 `remoteFileId` 和 `lockVersion`，发送 `DELETE /{remoteFileId}`，将 `lockVersion` 放入查询参数；不要求存在对应的本地文件 |

文件 ID 和锁版本不需要在环境文件中手工填写。内容覆盖和路径更新前会再次读取本地文件，确认大小、修改时间和 SHA-256 与规划一致；本地文件已变化或丢失时，记录原因并跳过。删除直接使用本轮规划中的远端元数据，不读取或删除本地源文件。

执行 `update` 会依次处理内容变化、路径变化和删除项，`all` 中的更新阶段采用相同顺序。`deleted` 以本轮完整清单为依据；`sourceDir` 应代表本次要同步的目录范围。

更新后若要再次执行写入，应先重新 `plan` 获取最新锁版本。使用旧规划重复执行 `update` 可能产生版本冲突或重复请求响应，脚本原样记录，不自动获取新版本重试。内容覆盖的幂等键由项目、本轮标识、文件 ID、锁版本、内容哈希及修改时间生成。

`update` 完成后不会自行调用模型；通过 `parse` 重新分析已变化的文件。后端会在内容或路径变化时使旧分析详情失效，后续解析生成新的详情。若同一轮还有新增文件，另外执行 `upload`，或直接使用 `all`。同时修改内容和路径的文件可能被规划为 `added` 与 `deleted`，脚本按规划分别上传新文件、删除旧文件，不自行推断移动关系。

## 观察记录

```text
output/{projectId}/{runId}/
├── manifest.json            # 最近一次本地扫描：上下文、清单、文件路径映射、过滤原因
├── plan.response.json       # 最近一次同步规划调用
├── uploads.jsonl            # 所有单文件上传尝试，逐行追加
├── updates.jsonl            # 所有内容覆盖、路径变更、删除及跳过记录，逐行追加
├── parse.response.json      # 最近一次解析调用
├── files.response.json      # 最近一次文件列表调用
└── requests/
    └── 时间戳-阶段-标识.json  # 每次调用的独立历史记录
```

请求记录包含方法、URL、查询参数、JSON 或表单参数、文件元数据、追踪 ID、HTTP 状态、响应正文以及耗时。上传和更新记录不复制文件正文，更新记录还保留对应的规划项；响应为非 JSON 时保留文本。认证令牌不写入记录。

每次请求开始时打印阶段与追踪 ID，结束后打印完整记录和文件路径。同轮再次查询时 `files.response.json` 指向最近一次调用，前后两次结果均可在 `requests/` 中找到。再次规划时 `manifest.json` 更新为最新扫描，历次提交的清单保留在对应规划调用的请求记录中。`output/` 默认保留，不自动清理，并已加入本目录的 Git 忽略规则。

HTTP 错误状态和业务错误响应均原样保存，不触发结果断言。上传阶段读取 `data.added`，更新阶段读取 `data.modified`、`data.moved` 和 `data.deleted`；如果缺少对应分类，当前阶段停止，`all` 随之停止。内容覆盖或路径变更缺少本地映射时留下跳过记录；三类更新缺少文件 ID 或锁版本时同样跳过。单文件调用出现本地读取问题、网络异常或业务错误时保留记录，继续下一个文件；这些阶段结束后，`all` 继续调用解析接口，由后端筛选可解析文件。网络请求不自动重试。

命令返回 `0` 表示调用过程结束，不代表业务结果正确。配置、前置文件或阶段衔接问题返回 `1`，用户中断返回 `130`。普通 HTTP 调用使用 120 秒超时，解析阶段与当前前端一致等待整批处理完成，可用 `Ctrl+C` 中断本地等待；中断不保证后端任务停止。

## 本地记录与 MinIO

| 阶段 | MinIO 中的变化 |
|---|---|
| `plan` | 无写入 |
| `upload` | 保存原始项目文件 |
| `update` | 内容覆盖会更新原始对象；仅移动目录时更新数据库路径，改名时后端复制到新对象并清理旧对象；内容或路径变化会清理旧分析详情并刷新索引；删除时后端移除原始对象和数据库文件记录、尝试清理分析详情并刷新索引 |
| `parse` | 保存文件分析详情，刷新项目规范和索引 |
| `files` | 无写入 |

MinIO 按项目和文件组织对象，不按本地 `runId` 创建结果目录。默认解析会跳过已有有效分析详情且未变化的文件；项目规范和索引按同一项目更新。删除本地记录不会删除 MinIO 对象。`project_test/` 仅作为源文件目录读取。
