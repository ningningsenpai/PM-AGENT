package com.ning.pm.agent.client.payload;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * AgentServiceChatRequest 对齐 Python 端 AgentChatRequest 的结构，
 * 用于向 agent-service 发送非流式对话请求。Python 侧字段使用 snake_case，
 * 这里通过 @JsonProperty 显式映射。
 *
 * @author ning
 * @date 2026-06-15
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AgentServiceChatRequest(
        @JsonProperty("conversation_id") String conversationId,
        @JsonProperty("messages") List<ChatMessagePayload> messages,
        @JsonProperty("context") ConversationContextPayload context,
        @JsonProperty("user") UserContextPayload user,
        @JsonProperty("stream") Boolean stream,
        @JsonProperty("use_tool_demo") Boolean useToolDemo
) {

    /** 单轮对话消息，对齐 Python 端 ChatMessage。 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ChatMessagePayload(
            @JsonProperty("role") String role,
            @JsonProperty("content") String content,
            @JsonProperty("name") String name
    ) {
    }

    /** 业务上下文，对齐 Python 端 ConversationContext。 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ConversationContextPayload(
            @JsonProperty("project_id") Long projectId,
            @JsonProperty("iteration_id") Long iterationId,
            @JsonProperty("task_id") Long taskId
    ) {
    }

    /** 用户身份，对齐 Python 端 UserContext。 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record UserContextPayload(
            @JsonProperty("user_id") String userId,
            @JsonProperty("tenant_id") String tenantId,
            @JsonProperty("user_name") String userName
    ) {
    }
}
