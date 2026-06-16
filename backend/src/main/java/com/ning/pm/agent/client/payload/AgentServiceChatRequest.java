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
        @JsonProperty("use_tool_demo") Boolean useToolDemo,
        @JsonProperty("token_usage_records") List<TokenUsagePayload> tokenUsageRecords,
        @JsonProperty("token_usage_summary") TokenUsageSummaryPayload tokenUsageSummary
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
            @JsonProperty("context_total_usage") Integer contextTotalUsage,
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

    /** 单轮 token 用量，对齐 Python 端 LLMTokenUsage。 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record TokenUsagePayload(
            @JsonProperty("provider") String provider,
            @JsonProperty("model") String model,
            @JsonProperty("round_index") Integer roundIndex,
            @JsonProperty("input_tokens") Integer inputTokens,
            @JsonProperty("output_tokens") Integer outputTokens,
            @JsonProperty("total_tokens") Integer totalTokens
    ) {
    }

    /** 会话累计 token 用量，对齐 Python 端 LLMTokenUsageSummary。 */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record TokenUsageSummaryPayload(
            @JsonProperty("total_input_tokens") Integer totalInputTokens,
            @JsonProperty("total_output_tokens") Integer totalOutputTokens,
            @JsonProperty("total_tokens") Integer totalTokens,
            @JsonProperty("rounds") Integer rounds
    ) {
    }
}
