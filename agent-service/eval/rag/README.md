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
export RAG_EMBED_FIELDS="memory_text"
export RAG_PAYLOAD_FIELDS="raw_id,global_index,project_id,project_name,turn_no,module,memory_type,business_type,status,memory_text,value_score,expected_retrieval_weight"
export RAG_FILTER_FIELDS="project_id"
```

## 3. 默认启动方式：PyCharm 直接运行脚本

当前 RAG 测试默认通过 PyCharm 直接运行两个脚本：

1. 先运行 `build_qdrant_index.py`，完成原始对话向量化并写入 Qdrant；
2. 再运行 `run_retrieval_eval.py`，对硬编码问题列表执行检索测试。

### 3.1 向量化脚本

文件：`agent-service/eval/rag/build_qdrant_index.py`

PyCharm Run Configuration 建议配置：

| 配置项 | 推荐值 |
|---|---|
| Script path | `agent-service/eval/rag/build_qdrant_index.py` |
| Working directory | `D:/Code/ning/PM-AGENT` |
| Environment variables | `DOUBAO_EMBEDDING_URL`、`DOUBAO_API_KEY`、`DOUBAO_EMBEDDING_MODEL`、`QDRANT_URL` |
| Parameters | 可留空，或按测试目标填写参数 |

向量化脚本支持以下参数：

| 参数 | 作用 | 示例 |
|---|---|---|
| `--collection` | 指定 Qdrant collection 名称 | `pm_agent_rag_eval_memory_text_v1` |
| `--embed-fields` | 指定参与 embedding 的字段，多个字段用英文逗号分隔 | `memory_text` |
| `--payload-fields` | 指定写入 Qdrant payload 的字段 | `raw_id,project_id,module,status,memory_text` |
| `--batch-size` | 指定批量写入 Qdrant 的数量 | `32` |

推荐第一轮默认参数：

```text
--collection pm_agent_rag_eval_memory_text_v1 --embed-fields memory_text
```

如果要测试“用户问题 + LLM 回答”参与向量化，可以把 Parameters 改为：

```text
--collection pm_agent_rag_eval_user_assistant_v1 --embed-fields user_message,assistant_message --payload-fields raw_id,project_id,module,business_type,status,memory_text
```

该脚本会：

1. 读取 `rag_raw_dialogues_v1.csv`；
2. 按 `--embed-fields` 指定字段拼接文本并调用豆包 Embedding API；
3. 重建指定 Qdrant collection；
4. 写入原始对话向量和 payload。

### 3.2 检索脚本

文件：`agent-service/eval/rag/run_retrieval_eval.py`

PyCharm Run Configuration 建议配置：

| 配置项 | 推荐值 |
|---|---|
| Script path | `agent-service/eval/rag/run_retrieval_eval.py` |
| Working directory | `D:/Code/ning/PM-AGENT` |
| Environment variables | 与向量化脚本相同 |
| Parameters | 可留空，或按测试目标填写参数 |

问题列表默认在 `run_retrieval_eval.py` 顶部硬编码：

```python
DEFAULT_QUESTIONS = [46, 47, 48, 49, 50, 51, 52, 53, 54, 55]
```

列表基于 `rag_questions_v1.csv` 的 `global_index`。如果只想在代码里固定测试问题，直接修改 `DEFAULT_QUESTIONS` 即可。

检索脚本支持以下参数：

| 参数 | 作用 | 示例 |
|---|---|---|
| `--collection` | 指定要检索的 Qdrant collection | `pm_agent_rag_eval_memory_text_v1` |
| `--top-k` | 指定召回条数 | `5` |
| `--filter-fields` | 指定 payload 精准筛选字段，字段值从问题数据中读取 | `project_id,module` |
| `--questions` | 临时覆盖硬编码问题列表 | `46,47,48` |

推荐第一轮默认参数：

```text
--collection pm_agent_rag_eval_memory_text_v1 --top-k 5 --filter-fields project_id
```

如果要测试模块级精准筛选，可以改为：

```text
--collection pm_agent_rag_eval_memory_text_v1 --top-k 5 --filter-fields project_id,module --questions 46,47,48
```

`--filter-fields` 表示从问题数据中取同名字段，组成 Qdrant payload 精准筛选条件。默认只按 `project_id` 过滤。

检索脚本输出内容包含：

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
- Parameters：可留空，或填写 `--collection pm_agent_rag_eval_memory_text_v1 --embed-fields memory_text`

### 5.2 检索配置

- Script path：`agent-service/eval/rag/run_retrieval_eval.py`
- Working directory：项目根目录 `D:/Code/ning/PM-AGENT`
- Environment variables：同上
- Parameters：例如 `--collection pm_agent_rag_eval_memory_text_v1 --top-k 5 --filter-fields project_id,module --questions 46,47,48`，也可以直接修改脚本顶部 `DEFAULT_QUESTIONS`

注意：运行检索前需要先启动 Qdrant，并先执行一次向量化脚本。

## 5. 当前测试边界

- 第一轮不调用 LLM；
- 第一轮不做图谱；
- 第一轮不移除 `project_id` 过滤；
- 第一轮只验证 Qdrant + 豆包 Embedding 的检索命中效果。
