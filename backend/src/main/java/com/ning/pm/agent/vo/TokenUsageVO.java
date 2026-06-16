package com.ning.pm.agent.vo;

/**
 * TokenUsageVO 单轮对话 token 用量视图。
 *
 * @author ning
 * @date 2026-06-15
 */
public record TokenUsageVO(
        Integer inputTokens,
        Integer outputTokens,
        Integer totalTokens
) {
}
