# 历史 AI 对话提炼为 RAG 原始数据集 CSV 提示词

```text
你是一名数据清洗与 RAG 评测数据构造助手。请从我提供的历史 AI 对话中，提炼出适合用于 RAG 检索测试的高价值对话记录，并输出为 CSV 格式。

如果你支持直接生成 `.csv` 文件，请直接生成文件。
如果你无法直接生成 `.csv` 文件，请输出可直接复制粘贴的 CSV 文本。该文本必须能被用户复制后保存为 `.csv` 文件，并能被 Excel、Python `csv` 模块或数据处理脚本直接读取。

## 任务目标

将历史 AI 对话整理成一个“RAG 原始数据集 CSV”。

要求：

1. 默认过滤掉无价值对话；
2. 保留对后续检索、项目复盘、知识沉淀有价值的内容；
3. 如果某条记录和具体项目无关，项目相关字段填写 `NULL`；
4. 不要编造原对话中没有的信息；
5. 如果无法判断某字段，填写 `NULL`；
6. 输出必须是标准 CSV，第一行是表头；
7. CSV 字段中的数组字段必须使用合法 JSON 数组字符串；
8. 如果字段内容包含逗号、换行或双引号，必须按 CSV 规范正确转义；
9. 不要输出解释，不要使用 Markdown 代码块包裹 CSV 文本；
10. 不要输出被过滤掉的低价值对话。

## 保留规则

优先保留：

- 项目需求讨论；
- 模块设计方案；
- 技术选型；
- 架构决策；
- Bug 定位与修复方案；
- 风险分析；
- 任务拆解；
- 状态更新；
- Prompt、Agent、RAG、向量检索、图谱等 AI 工程设计；
- 数据库、接口、前后端、部署、测试相关结论；
- 用户明确确认过的最终方案；
- 多轮对话中后来更新、推翻、替代旧结论的记录。

默认过滤：

- 闲聊；
- 打招呼；
- 简单确认，如“好的”“继续”“可以”；
- 没有结论的临时讨论；
- 明显重复且没有新增信息的内容；
- 纯格式调整但没有业务或技术价值的内容；
- 与学习、项目、技术、产品、设计、研究无关的话题；
- 只有情绪表达，没有可复用信息的内容。

## 输出字段

请严格按以下表头输出 CSV：

raw_id,global_index,project_id,project_name,turn_no,module,memory_type,business_type,status,user_message,assistant_message,memory_text,entities,facts,decisions,risks,supersedes_raw_id,value_score,expected_retrieval_weight

## 字段填写规则

### raw_id

唯一编号，从 001 开始递增：

RAW-HISTORY-001
RAW-HISTORY-002
RAW-HISTORY-003

### global_index

全局序号，从 1 开始递增。

### project_id

如果能判断具体项目，自行生成稳定编号，例如：

P-PM-AGENT
P-STUDY-RAG
P-DORM-SYSTEM

如果无法判断具体项目，填写 `NULL`。

### project_name

填写项目名称。

如果无法判断具体项目，填写 `NULL`。

### turn_no

该项目或该主题内的序号。

如果无法按项目分组，可以直接等于 `global_index`。

### module

填写对话所属模块或主题，例如：

用户认证、任务管理、RAG 检索、事件图谱、前端页面、数据库设计、论文阅读、Bug 修复、部署配置、学习笔记。

如果无法判断，填写 `NULL`。

### memory_type

只允许填写：

semantic
episodic
procedural

判断规则：

- `semantic`：稳定事实、设计结论、技术方案、Bug 根因、最终决策；
- `episodic`：某次讨论过程、阶段性状态、临时分析；
- `procedural`：操作方法、使用习惯、流程步骤、工具配置方法。

### business_type

只允许填写：

requirement
decision
task
risk
bug
status_update
progress
learning
architecture
prompt
rag
tool_usage
other

判断规则：

- `requirement`：需求或功能范围；
- `decision`：明确方案或取舍；
- `task`：任务拆解；
- `risk`：风险、隐患、限制；
- `bug`：Bug、错误、异常、修复；
- `status_update`：状态变化、最新结论；
- `progress`：项目进度；
- `learning`：学习笔记、论文理解、概念解释；
- `architecture`：系统架构、模块边界；
- `prompt`：提示词设计；
- `rag`：RAG、向量检索、Embedding、召回、reranker；
- `tool_usage`：工具、命令、软件使用方法；
- `other`：其他有价值内容。

### status

只允许填写：

active
superseded
conflicted
expired

如果不确定，默认填写 `active`。

### user_message

保留原始用户问题或用户表达。

如果原始对话很长，请提炼为忠实摘要，不要改变含义。

### assistant_message

保留 AI 的回答或结论，不要只写一句话摘要。

要求：

- 至少保留核心结论、关键原因、执行步骤、边界条件和注意事项；
- 如果原始回答包含方案、流程、字段、指标、风险或示例，需要尽量压缩后保留；
- 单条 `assistant_message` 建议保持 80 到 300 个中文字符；
- 对高价值设计类、架构类、Bug 修复类、RAG/Agent 类内容，可以保留更长摘要；
- 允许压缩冗余表达，但不能省略影响后续检索判断的关键信息；
- 不要编造原对话中没有的信息。

### memory_text

用于后续向量化的合并文本。请按以下格式生成：

项目：{project_name}。模块：{module}。用户问题：{user_message}。LLM回答：{assistant_message}

如果项目为空：

项目：NULL。模块：{module}。用户问题：{user_message}。LLM回答：{assistant_message}

### entities

JSON 数组字符串，提取关键实体。

例如：

["RAG", "Embedding", "Qdrant", "Recall@K"]

如果没有明确实体，填写：

[]

### facts

JSON 数组字符串，提取稳定事实。

例如：

["Qdrant point 由 vector 和 payload 组成", "project_id 用于过滤检索范围"]

如果没有，填写：

[]

### decisions

JSON 数组字符串，提取明确决策。

例如：

["第一轮 RAG 测试只评估检索效果，不调用 LLM"]

如果没有，填写：

[]

### risks

JSON 数组字符串，提取风险或注意事项。

例如：

["无关问题也会被向量库返回 topK，需要后续加入相似度阈值"]

如果没有，填写：

[]

### supersedes_raw_id

如果当前记录替代了某条旧记录，填写旧记录的 `raw_id`。

如果没有替代关系，填写空字符串 `""`。

### value_score

填写 0 到 1 之间的小数，表示长期记忆价值。

参考标准：

0.90-1.00：关键架构、重要决策、Bug 根因、最终方案
0.75-0.89：模块设计、需求范围、风险分析、重要学习结论
0.50-0.74：阶段性讨论、一般任务拆解、普通操作方法
0.30-0.49：弱价值内容，但仍可能有参考意义
低于 0.30：通常不应输出

默认过滤掉低于 `0.30` 的内容。

### expected_retrieval_weight

只允许填写：

high
medium
low

判断规则：

- `high`：后续很可能被检索使用；
- `medium`：有一定参考价值；
- `low`：价值较低但仍保留。

## 多轮更新处理规则

如果同一主题出现多轮更新，请保留关键链路：

1. 初始方案；
2. 中间变更；
3. 最终结论。

如果最终结论替代了旧方案：

- 旧方案记录的 `status` 填 `superseded`；
- 最终结论记录的 `status` 填 `active`；
- 最终结论记录的 `supersedes_raw_id` 填旧方案的 `raw_id`。

## 输出要求

1. 优先直接生成 `.csv` 文件；
2. 如果无法直接生成 `.csv` 文件，请输出可直接复制粘贴的 CSV 文本；
3. 可粘贴 CSV 文本第一行必须是表头；
4. 不要输出解释；
5. 不要使用 Markdown 代码块包裹 CSV 文本；
6. 不要省略表头；
7. 不要输出被过滤掉的低价值对话；
8. 保证每行字段数量一致；
9. JSON 数组字段必须合法；
10. 中文内容保持原意，允许压缩但不要编造。

## 示例输出格式

raw_id,global_index,project_id,project_name,turn_no,module,memory_type,business_type,status,user_message,assistant_message,memory_text,entities,facts,decisions,risks,supersedes_raw_id,value_score,expected_retrieval_weight
RAW-HISTORY-001,1,P-PM-AGENT,PM-Agent 智能项目管理 Agent 平台,1,RAG 检索,semantic,rag,active,RAG 测试需要哪些数据集？,需要原始数据集、问题集合和标准答案集合，其中标准答案应包含正确 doc_id 和必答事实。,项目：PM-Agent 智能项目管理 Agent 平台。模块：RAG 检索。用户问题：RAG 测试需要哪些数据集？。LLM回答：需要原始数据集、问题集合和标准答案集合，其中标准答案应包含正确 doc_id 和必答事实。,"[""RAG"",""原始数据集"",""问题集合"",""标准答案集合""]","[""RAG 检索测试至少需要原始数据集、问题集合和标准答案集合""]","[""标准答案集合需要包含正确 doc_id 和必答事实""]",[],"",0.92,high

请处理我接下来提供的历史对话内容，并输出 CSV。
```
