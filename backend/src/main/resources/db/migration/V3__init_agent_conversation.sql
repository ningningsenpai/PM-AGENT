-- 第 3 阶段：Agent 对话记录表
-- 设计要点：
-- 1. 每一轮对话（一次 user 提问 + 对应 assistant 回答）落一条记录，user 与 assistant 各占独立字段；
-- 2. 同一 conversation_id 下通过 iteration_id 区分对话内部的「轮次/会话片段」，由 Java 侧维护；
-- 3. 记录该轮对话的 input/output/total token 数量，供成本统计与上下文窗口控制；
-- 4. 其余字段参考 AgentChatRequest 结构落地：项目上下文、用户上下文、模型、工具开关、trace 等。

CREATE TABLE agent_conversation_message (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    conversation_id VARCHAR(64) NOT NULL COMMENT '会话 ID，对应 AgentChatRequest.conversation_id',
    iteration_id BIGINT NOT NULL DEFAULT 0 COMMENT '对话内部轮次 ID，区分同一会话下的多轮对话片段',
    turn_index INT NOT NULL DEFAULT 0 COMMENT '该轮次内的消息序号，从 0 开始递增',
    project_id BIGINT NULL COMMENT '业务上下文：项目 ID',
    task_id BIGINT NULL COMMENT '业务上下文：任务 ID',
    user_id BIGINT NULL COMMENT '提问用户 ID（与 pm_user.id 对应，匿名时为 NULL）',
    user_name VARCHAR(64) NULL COMMENT '提问用户展示名称',
    user_content MEDIUMTEXT NOT NULL COMMENT '本轮用户输入内容',
    assistant_content MEDIUMTEXT NULL COMMENT '本轮 assistant 回答内容；调用失败或仅触发工具时可为空',
    model VARCHAR(64) NULL COMMENT '本轮使用的模型标识，例如 deepseek-chat',
    input_tokens INT NOT NULL DEFAULT 0 COMMENT '本轮 prompt 输入 token 数',
    output_tokens INT NOT NULL DEFAULT 0 COMMENT '本轮 completion 输出 token 数',
    total_tokens INT NOT NULL DEFAULT 0 COMMENT '本轮 input + output 合计 token 数',
    use_tool_demo TINYINT NOT NULL DEFAULT 0 COMMENT '是否强制演示工具调用，对应 AgentChatRequest.use_tool_demo',
    stream TINYINT NOT NULL DEFAULT 0 COMMENT '是否流式输出，对应 AgentChatRequest.stream',
    tool_calls JSON NULL COMMENT '本轮工具调用记录，JSON 数组',
    status VARCHAR(32) NOT NULL DEFAULT 'success' COMMENT '调用状态：success / failed',
    error_message VARCHAR(512) NULL COMMENT '失败原因摘要',
    trace_id VARCHAR(64) NULL COMMENT '链路追踪 ID，对应响应 traceId',
    created_by BIGINT NULL COMMENT '创建人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT NULL COMMENT '更新人 ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    KEY idx_acm_conversation (tenant_id, conversation_id, iteration_id, turn_index),
    KEY idx_acm_project (tenant_id, project_id, deleted),
    KEY idx_acm_user (tenant_id, user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Agent 对话消息表（一轮 user+assistant 一行）';
