# 内容归一化评估

该目录保存内容归一化固定样例、效果评估和术语库发布检查入口。

```bash
cd agent-service
python -m eval.normalization.evaluate
python -m eval.normalization.release_check
```

`evaluate.py` 输出 Precision、Recall、F1 和平均处理耗时；`release_check.py` 先执行结构与冲突校验，再检查指标是否达到发布阈值。发布检查通过不代表自动修改词库状态，正式发布仍需人工审阅和代码提交。
