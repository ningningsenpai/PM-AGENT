# 项目助手闭环调试

本目录模拟前端通过 HTTP 执行流程。固定样本在 `fixtures/`，原有 `project_test/` 不会被修改。结果全部保留在 `output/<campaign>/round-NNN/`；密钥和完整运行记录不提交 Git。

## 启动独立环境

在仓库根目录执行，按需替换 Python 路径：

```powershell
$flowPython = "D:\Code\ning\PM-AGENT\agent-service\.venv\Scripts\python.exe"
$flowEnv = "D:\Code\ning\PM-AGENT\agent-service\tests\project_assistant_flow\environment.py"
$flowScript = "D:\Code\ning\PM-AGENT\agent-service\tests\project_assistant_flow\run.py"
& $flowPython $flowEnv configure --campaign mvp-20260908
docker compose --env-file agent-service/tests/project_assistant_flow/.env.local -f agent-service/tests/project_assistant_flow/docker-compose.yml up -d
& $flowPython $flowEnv check --campaign mvp-20260908
& $flowPython $flowEnv migrate --campaign mvp-20260908
& $flowPython $flowEnv serve --campaign mvp-20260908
```

服务会读取已有 `.env` 中的模型配置和 DeepSeek 密钥，同时覆盖数据库、Redis、MinIO 及测试费用账本的连接。`check` 实际连接 MySQL、ping Redis、写读测试 MinIO 对象；容器刚启动时需等待数据库初始化完成再检查。MySQL 8 默认鉴权需要 `cryptography`，依赖安装按仓库开发环境流程执行。

`serve` 不开启 reload。修改代码后，停止本目录启动的 18080 实例，再重新运行。不要终止其他项目或原有 8000 服务。

## 分阶段调用

```powershell
& $flowPython $flowScript all --campaign mvp-20260908 --round round-001
& $flowPython $flowScript status --campaign mvp-20260908 --round round-001
& $flowPython $flowScript retry --campaign mvp-20260908 --round round-001 --file-ids 1,2
& $flowPython $flowScript tools --campaign mvp-20260908 --round round-001
& $flowPython $flowScript tool-cases --campaign mvp-20260908 --round round-001
& $flowPython $flowScript trace --campaign mvp-20260908 --round round-001
& $flowPython $flowScript verify --campaign mvp-20260908 --round round-001
```

阶段顺序：`setup → plan → upload → update → parse → status → conversation → tools → tool-cases → learn → reports → correct → verify`。`all` 从检查点跳过已完成阶段。单独执行阶段会再次调用，适合定位问题；每个请求生成独立记录，旧记录不覆盖。

`update` 是测试脚本聚合指令，实际调用已有内容覆盖和 DELETE 接口。本固定样本先上传一个中间版本和待删除文件，再恢复标准内容，验证覆盖与删除路径。最终六个文件与 `fixtures/` 一致。

`tool-cases` 会让模型选择目标只读工具；只有轨迹中真实成功的调用才算覆盖。学习由 `learn` 显式触发。`verify` 检查权限、幂等、条目版本/期限、跨项目范围、工具协议和证据定位，不代替报告事实人工审阅。详见 [基准与验收](基准与验收.md)。

## 费用与归档

测试后端每次调用前预留预算，账本固定在活动目录，重启或新轮次不会清零。未知 usage 的失败请求保留保守估算。活动累计达到 30 元前停止新的付费请求；不要通过换活动 ID 绕过本次授权预算。

每轮保留源码和配置指纹、项目/会话/runId、HTTP 请求、模型与工具轨迹、文件/条目状态、Markdown 报告、自动检查和人工事实审阅结果。源码或 Prompt 修改后重新计算连续通过轮次；最终结论需连续三轮满足固定基准，不能把脚本正常退出当作全面验收。
