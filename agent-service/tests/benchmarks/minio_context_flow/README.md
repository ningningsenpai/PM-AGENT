# MinIO 上下文主链路基准

本目录验证正式服务是否真实更新和召回 MinIO 上下文，不以 MySQL 行记录代替业务闭环。

## 前置条件

- MySQL、Redis、MinIO 已按 `deploy/` 配置运行；
- Alembic 已升级到当前版本；
- 后端已启用文件语义分析和 DeepSeek；
- 后端地址默认为 `http://127.0.0.1:8000`。

## 执行七轮主链路

```powershell
python tests/benchmarks/minio_context_flow/run_baseline.py `
  --base-url http://127.0.0.1:8000
```

脚本创建独立用户和项目，依次验证初始化、初次解析、无变化重跑、权威文档更新、代码更新边界、明确规则写入以及偏好确认和项目召回。

## 执行三轮召回 A/B

```powershell
python tests/benchmarks/minio_context_flow/run_retrieval_ab.py `
  --baseline tests/benchmarks/minio_context_flow/output/<运行目录>/baseline-summary.json
```

脚本在同一份真实 MinIO 快照上比较生产词法召回、稀疏字符向量余弦召回和 65/35 混合召回，并输出 Recall@3、MRR 和保留方案。

## 输出

每次运行写入 `output/<时间>/`：

- `baseline-summary.json`：七轮请求、MinIO 对象、规则、记忆、请求计划、回答和断言；
- `baseline-failure.json`：失败时保存已完成轮次与异常；
- `retrieval-ab-summary.json`：三轮候选、各算法排序、指标和最终选择。

`output/` 是本地实测证据目录，不进入 Git。正式汇总结论维护在 `design-docs/13-MinIO主链路十轮基准与召回对比报告.md`。
