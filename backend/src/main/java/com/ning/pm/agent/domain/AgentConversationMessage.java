package com.ning.pm.agent.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

/**
 * AgentConversationMessage 对应 agent_conversation_message 表，
 * 每条记录承载一轮 user + assistant 对话以及该轮次的 token 用量。
 *
 * @author ning
 * @date 2026-06-15
 */
@Getter
@Setter
@TableName("agent_conversation_message")
public class AgentConversationMessage extends BaseEntity {

    /** 会话 ID，对应 AgentChatRequest.conversation_id。 */
    private String conversationId;

    /** 对话内部轮次 ID，由 Java 侧维护，用于区分同一会话的多轮对话片段。 */
    private Long iterationId;

    /** 该轮次内消息序号，从 0 开始递增。 */
    private Integer turnIndex;

    /** 业务上下文：项目 ID。 */
    private Long projectId;

    /** 业务上下文：任务 ID。 */
    private Long taskId;

    /** 提问用户 ID。 */
    private Long userId;

    /** 提问用户展示名称。 */
    private String userName;

    /** 本轮用户输入内容。 */
    private String userContent;

    /** 本轮 assistant 回答内容。 */
    private String assistantContent;

    /** 本轮模型标识。 */
    private String model;

    /** 本轮 prompt 输入 token 数。 */
    private Integer inputTokens;

    /** 本轮 completion 输出 token 数。 */
    private Integer outputTokens;

    /** 本轮 input + output 合计 token 数。 */
    private Integer totalTokens;

    /** 是否强制演示工具调用。 */
    private Integer useToolDemo;

    /** 是否流式输出。 */
    private Integer stream;

    /** 本轮工具调用记录，JSON 数组字符串。 */
    private String toolCalls;

    /** 调用状态：success / failed。 */
    private String status;

    /** 失败原因摘要。 */
    private String errorMessage;

    /** 链路追踪 ID。 */
    private String traceId;
}
