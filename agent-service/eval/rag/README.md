# RAG 检索测试说明

本目录用于第一轮 RAG 向量检索效果测试，只验证“历史材料向量化、问题检索、命中信息输出”，暂不调用 LLM 生成最终回答。

## 1. 前置条件

需要准备：

- 豆包 Embedding API；
- Qdrant 服务，例如 Docker 启动在 `http://localhost:6333`；
- `agent-service/eval/data/` 下的三份数据集：
  - `rag_raw_dialogues_v1.csv`
  - `rag_questions_v1.csv`
  - `rag_gold_answers_v1.csv`

## 2. 环境变量

请根据你的豆包配置设置：

```bash
export DOUBAO_EMBEDDING_URL="你的豆包 embedding endpoint"
export DOUBAO_API_KEY="你的豆包 API Key"
export DOUBAO_EMBEDDING_MODEL="你的豆包 embedding 模型名"
```

可选配置：

```bash
export QDRANT_URL="http://localhost:6333"
export QDRANT_COLLECTION="pm_agent_rag_eval_v1"
export RAG_TOP_K="5"
```

## 3. 一键完成初始文件向量化

在仓库根目录执行：

```bash
python agent-service/eval/rag/build_qdrant_index.py
```

该命令会：

1. 读取 `rag_raw_dialogues_v1.csv`；
2. 使用 `memory_text` 调用豆包 Embedding API；
3. 重建 Qdrant collection；
4. 写入原始对话向量和 payload。

payload 中保留：

- `raw_id`
- `project_id`
- `project_name`
- `module`
- `status`
- `memory_text`

## 4. 一键启动规定范围检索

问题范围在 `run_retrieval_eval.py` 顶部用全局变量控制：

```python
START_INDEX = 1
END_INDEX = 10
```

范围基于 `rag_questions_v1.csv` 的 `global_index`，从 1 开始，包含结束值。

例如检索第 1 到第 10 个问题，先把代码改成：

```python
START_INDEX = 1
END_INDEX = 10
```

然后执行：

```bash
python agent-service/eval/rag/run_retrieval_eval.py --top-k 5
```

输出内容包含：

- 问题编号；
- 输入的问题；
- 检索出的原始数据编号；
- 检索出的原文；
- 正确的编号；
- 正确编号对应的原文；
- 和预计答案对比的相似度。

相似度暂按以下方式计算：

```text
命中的正确编号数量 / 检索出的编号数量
```

检索结果只输出到控制台，不再写入 CSV 文件。

## 5. PyCharm 启动方式

可以直接在 PyCharm 启动，推荐配置两个 Run Configuration。

### 5.1 向量化配置

- Script path：`agent-service/eval/rag/build_qdrant_index.py`
- Working directory：项目根目录 `D:/Code/ning/PM-AGENT`
- Environment variables：填写豆包和 Qdrant 配置，例如 `DOUBAO_EMBEDDING_URL`、`DOUBAO_API_KEY`、`DOUBAO_EMBEDDING_MODEL`、`QDRANT_URL`
- Parameters：可留空，或填写 `--collection pm_agent_rag_eval_v1`

### 5.2 检索配置

- Script path：`agent-service/eval/rag/run_retrieval_eval.py`
- Working directory：项目根目录 `D:/Code/ning/PM-AGENT`
- Environment variables：同上
- Parameters：例如 `--top-k 5`，问题范围在脚本顶部 `START_INDEX` 和 `END_INDEX` 中修改

注意：运行检索前需要先启动 Qdrant，并先执行一次向量化脚本。

## 6. 当前测试边界

- 第一轮不调用 LLM；
- 第一轮不做图谱；
- 第一轮不移除 `project_id` 过滤；
- 第一轮只验证 Qdrant + 豆包 Embedding 的检索命中效果。
