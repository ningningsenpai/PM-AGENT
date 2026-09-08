# PM-Agent 前端工程

Vue 3、TypeScript、Naive UI、Pinia、Vue Router、Axios 和 Vite 组成前端运行栈。页面沿用 Warm Linear 视觉，桌面优先，适配 1280px 及以上工作区。

## 启动与验证

使用 Node.js 20 和 pnpm 9：

```powershell
pnpm install
Copy-Item .env.example .env
pnpm dev
pnpm typecheck
pnpm test
pnpm build
```

示例配置默认连接真实接口，开发服务器将 /api 代理到 http://localhost:8000。VITE_API_BASE_URL 留空，避免绕过代理产生跨域问题。独立验收后端可以通过启动进程的环境变量选择：

```powershell
$env:VITE_PROXY_TARGET = 'http://127.0.0.1:18080'
$env:VITE_USE_MOCK = 'false'
pnpm dev
```

生产部署需要由网关把 /api 转发到 FastAPI，并将前端页面路径回退到 index.html。不要把模型密钥、数据库或存储凭据写入 VITE_ 变量。

## 页面与职责

| 路径 | 功能 |
|---|---|
| / | 介绍及明确标记的设计预览 |
| /login、/register | 邮箱登录、注册 |
| /overview | 真实项目数量、当前项目文件与报告摘要 |
| /projects | 创建、筛选与选择项目 |
| /projects/:id | 文件同步、解析状态、定向重试、读取文件及删除项目 |
| /projects/:id/assistant | 持久化问答、工具记录、显式学习及学习内容纠正 |
| /projects/:id/reports | 开发／风险报告生成、历史详情、来源与运行 |
| /projects/:id/knowledge | 项目文件及已学习内容 |
| /projects/:id/risk | 风险报告入口和风险处置的未开放说明 |
| /projects/:id/tasks | 真实模式仅提供禁用看板结构 |
| /profile | 资料修改；tab=security 为密码修改 |
| /settings | 尚未开放的配置能力说明 |

业务代码位于 src/modules，所有业务请求经过 src/api/http.ts。新增页面使用独立业务模块、类型和 API 文件。

## 接口与状态约定

- 当前后端成功业务码为 **200**；HTTP 成功后仍需检查运行状态。旧设计文档中的 code=0 已纠正。
- 邮箱必填，注册字段为 username、email、password；密码为 6～64 位。
- 用户、项目、会话、消息、运行、报告、学习条目的雪花 ID 均为字符串，文件 ID 和版本号为数字。
- 路由中的项目 ID 决定访问范围；切换项目销毁页面作用域，迟到结果不写回新页面。
- 20001 与 HTTP 401 统一处理登录失效；错误展示中文提示、错误码和 traceId。
- 同步与解析分开操作。文件解析不会创建任务，初始化状态不是业务进度。
- 问答、学习和报告使用持久化普通 HTTP 接口。当前未接通 SSE。
- 长操作具有独立超时，不展示模拟进度；文件上传进度只表示已处理的同步项。
- 学习纠正传 version 和 reason；文件变更传 lockVersion。内容提交成功但快照失败时单独提示，可重发快照。
- Markdown 禁用原始 HTML 和图片加载，链接使用独立标签页及 noopener/noreferrer。

## 运行恢复

会话和报告数据由后端持久化。前端把未确认操作的类型、内容、幂等键及已知 runId 暂存于 sessionStorage，以用户、项目和会话隔离；终态会清除暂存内容，退出登录清理本地恢复记录。

请求中断时，优先通过已知 runId 查询；未知 runId 时点击“查询 / 恢复”会使用原内容、原幂等键恢复请求。服务端负责确保同一操作仅执行一次。明确失败后，用户重新执行才建立新键。关闭浏览器标签页会失去该页的 sessionStorage；历史消息及报告仍可从后端重新打开。

文件同步沿用既有同步计划与防重逻辑。删除必须确认；非删除操作部分失败时跳过远端删除。版本冲突或结果不明时，刷新核对状态后再操作。

## 测试边界

pnpm test 使用 Node 内置测试运行器及现有 Vite 构建依赖，验证实际响应码、ID 精度、认证失效、幂等恢复、并发保护、项目隔离、版本参数及 Markdown 安全；不调用模型、不访问业务数据库。

固定浏览器验收样本位于 tests/fixtures/project。真实接口、浏览器验收及限制记录在 [前端闭环实现与验收](../docs/25-前端闭环实现与验收.md)。

VITE_USE_MOCK=true 仅用于标记明确的本地演示。助手、报告、学习纠正、密码修改等能力需要真实服务；演示模式不返回虚假的保存成功。
