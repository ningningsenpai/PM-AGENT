package com.ning.pm.agent.vo;

/**
 * AgentChatVO 返回给前端的 Agent 对话结果。
 *
 * @author ning
 * @date 2026-06-15
 */
public record AgentChatVO(

        /** 会话 ID。 */
        String conversationId,

        /** 对话轮次 ID。 */
        Long iterationId,

        /** 本轮序号，从 0 开始。 */
        Integer turnIndex,

        /** assistant 回答内容。 */
        String answer,

        /** 本轮使用的模型标识。 */
        String model,

        /** 本轮 token 用量。 */
        TokenUsageVO usage
) {
}
