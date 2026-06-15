package com.ning.pm.agent.client.payload;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

/**
 * AgentServiceChatResponse 对齐 Python 端 ApiResponse&lt;ChatResponse&gt; 的整体结构，
 * 包含 traceId 与 data 中的回答内容、token 用量、工具调用。
 *
 * @author ning
 * @date 2026-06-15
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AgentServiceChatResponse(
        @JsonProperty("code") Integer code,
        @JsonProperty("message") String message,
        @JsonProperty("data") ChatData data,
        @JsonProperty("traceId") String traceId
) {

    /** 对齐 Python 端 ChatResponse。 */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ChatData(
            @JsonProperty("answer") String answer,
            @JsonProperty("model") String model,
            @JsonProperty("conversation_id") String conversationId,
            @JsonProperty("tool_calls") List<ToolCall> toolCalls,
            @JsonProperty("usage") TokenUsage usage
    ) {
    }

    /** 对齐 Python 端 ToolCallRecord。 */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ToolCall(
            @JsonProperty("tool_name") String toolName,
            @JsonProperty("input") Map<String, Object> input,
            @JsonProperty("output") Map<String, Object> output,
            @JsonProperty("status") String status
    ) {
    }

    /** 对齐 Python 端 TokenUsage。 */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record TokenUsage(
            @JsonProperty("input_tokens") Integer inputTokens,
            @JsonProperty("output_tokens") Integer outputTokens,
            @JsonProperty("total_tokens") Integer totalTokens
    ) {
    }
}
