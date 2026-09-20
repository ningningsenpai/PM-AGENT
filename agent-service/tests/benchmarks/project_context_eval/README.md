# 单项目上下文评测

本目录把 `agent-service/project_test` 作为只读原型，建立三个可复现版本、50 个冻结问题、人工证据标注和 A0～A3 检索实验。它的目标不是证明单个小样本具有外部普适性，而是先把评测方法、数据血缘和统计口径跑通，再扩展到更多项目类型。

## 数据布局

```text
project_context_eval/
├── fixtures/student_management/
│   ├── v1/version.json              原型哈希锁定
│   ├── v2/overlay/                  档案维护增量
│   └── v3/overlay/                  工程加固增量
├── dataset/
│   ├── questions.jsonl              50 个冻结问题
│   ├── annotations.jsonl            人工文件、证据锚点和答案要点
│   └── freeze.json                  数据集和版本快照哈希
├── output/                           本地原始运行记录，Git 忽略
└── reports/                          可提交的阶段结论
```

原始 `project_test` 不会被复制回写。物化器先复制原型，再顺序应用 v2/v3 覆盖层；`backend/target`、`frontend/dist`、依赖目录和缓存不进入语料。

## 冻结集构成

| 类型 | 数量 |
|---|---:|
| 直接事实 | 8 |
| 同义改写 | 8 |
| 跨文件 | 10 |
| 错误前提 | 6 |
| 无答案 | 6 |
| 历史状态 | 6 |
| 精确代码定位 | 6 |
| 合计 | 50 |

开发集 35 题，留出集 15 题。问题文本不进入项目语料。标注使用唯一原文锚点，运行前解析为真实行号并记录内容哈希。

## 算法定义

- A0：复用生产查询归一化、召回计划和 6/3/1 字段评分的离线适配器。
- A1：BM25F，路径/标题/标题行/正文权重固定为 3/3/2/1。
- A2：A0 与 A1 的 RRF 融合，`k=60`。
- A3：对 A2 Top-10 做结构化模型重排，相关度为 0～3。
- A4：预留给语义向量混合召回；只有 A0～A3 质量门禁通过后才运行。

A0 的离线适配器在物化文件全文上评分，不等同于 MinIO 解析后的生产候选。正式结论必须同时报告离线结果与真实 API 结果。

## 运行

在 `agent-service` 下执行：

```powershell
.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.validate_dataset `
  --workdir tests/benchmarks/project_context_eval/output/validation/work `
  --output tests/benchmarks/project_context_eval/output/validation/result.json

.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.run_offline `
  --output tests/benchmarks/project_context_eval/output/<run-id> `
  --algorithms A0 A1 A2 `
  --with-ablations

.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.run_offline `
  --output tests/benchmarks/project_context_eval/output/<a3-run-id> `
  --algorithms A3
```

A3 会把 A2 Top-10 的脱敏文件片段发给配置的 DeepSeek。发送前复用生产敏感信息处理器，阻断私钥并掩码常见密码、Token 和 API Key；仍必须取得对外发送本地测试代码的明确授权。

每个运行目录保留：

- `aggregate.json`：总指标、开发/留出分组、延迟、模型用量和局限；
- `query-runs.jsonl`：逐问题排名、分数、耗时、模型事件和错误；
- `resolved-annotations.json`：证据真实行号与文件哈希；
- `fixtures/`：该次运行实际使用的完整版本快照。

真实链路与回答裁判在取得对外发送授权后执行：

```powershell
.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.run_live `
  --output tests/benchmarks/project_context_eval/output/<live-run-id> `
  --parse --ask --allow-external-model-data

.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.summarize_live `
  --live-output tests/benchmarks/project_context_eval/output/<live-run-id>

.\.venv\Scripts\python.exe -m tests.benchmarks.project_context_eval.evaluate_answers `
  --live-output tests/benchmarks/project_context_eval/output/<live-run-id> `
  --output tests/benchmarks/project_context_eval/output/<judge-run-id> `
  --allow-external-model-data
```

真实问答按题创建独立会话，避免历史答案污染后续问题。`summarize_live` 会补采解析运行轨迹并汇总解析与问答的 Token、费用和延迟；`evaluate_answers` 对 Agent 失败按零覆盖计入，并对成功回答统计无答案识别、要点、引用和忠实度。

## 首轮质量门禁

进入 A4 前至少满足：

- 数据集、证据锚点与三版快照哈希校验全部通过；
- A0～A3 无运行错误；
- 留出集 Recall@8 不低于 0.85，MRR 不低于 0.70；
- A3 相比 A0 在 MRR 或 NDCG@8 至少一项有正提升，且 Recall@8 不下降超过 0.02；
- 无答案识别 F1 不低于 0.80；
- 引用正确率不低于 0.90，回答忠实度不低于 0.85；
- P95 延迟、输入/输出 Token 和人民币费用均有完整记录。

无答案、引用与忠实度属于回答阶段指标，不能由文件级召回结果替代。

首轮完整结果见 [A0～A3 首轮评测报告](reports/2026-09-20-A0-A3首轮评测报告.md)。首轮端到端门禁未通过，因此尚未执行 A4。
