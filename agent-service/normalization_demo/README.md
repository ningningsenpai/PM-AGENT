# Aho-Corasick 词库匹配 Demo

本目录用于验证 PM-Agent 内容归一化技术路线的第一步：只做公共词库命中，不提前引入完整 RAG、向量库或复杂检索基础设施。

## 阶段目标

当前阶段只回答一个问题：

> 给定一批 PM-Agent 公共词库词条，用户输入中能否稳定命中标准概念？

## 文件说明

| 文件 | 说明 |
|---|---|
| `lexicon.json` | 实验词库，维护标准词、别名、分类和标签 |
| `aho_match_demo.py` | Aho-Corasick 词库匹配封装和单条文本 demo |
| `evaluation_cases.json` | 第一阶段评估用例 |
| `evaluate_aho_match.py` | 批量评估脚本，输出 precision、recall、F1 |

## 安装依赖

在 `agent-service` 目录执行：

```bash
python -m pip install -e .
```

如果只想临时安装 demo 依赖：

```bash
python -m pip install pyahocorasick
```

## 运行单条 demo

```bash
cd agent-service
python -m normalization_demo.aho_match_demo
```

## 运行评估

```bash
cd agent-service
python -m normalization_demo.evaluate_aho_match
```

输出中重点看：

| 字段 | 含义 |
|---|---|
| `precision` | 命中的标准词里有多少是正确的 |
| `recall` | 期望标准词里有多少被命中 |
| `f1` | precision 和 recall 的综合指标 |
| `missed` | 漏召词，后续需要补词库或接入分词 |
| `extra` | 误召词，后续需要调整词库或冲突规则 |

## 分步引进策略

| 阶段 | 能力 | 评估重点 |
|---|---|---|
| 第一步 | Aho-Corasick 词库匹配 | 标准词命中率、漏召、误召 |
| 第二步 | 最大正向匹配分词 | 中文领域短语是否切准 |
| 第三步 | 同义词归一化 | 不同说法是否归到同一标准概念 |
| 第四步 | BM25F 字段加权召回 | 召回文件是否命中正确模块和实体 |
| 第五步 | SimHash 近重复判断 | 是否能过滤重复摘要、风险候选和任务草稿 |

每一步都沿用同一套评估格式：输入样例、期望结果、实际结果、precision、recall、F1。
