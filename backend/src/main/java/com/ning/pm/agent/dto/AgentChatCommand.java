package com.ning.pm.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * AgentChatCommand 是前端发起对话的请求体。
 *
 * <p>本期仅对外暴露最小必要参数；其余字段（stream/use_tool_demo/system 提示等）
 * 由服务端按业务策略自动组装。
 *
 * @author ning
 * @date 2026-06-15
 */
public record AgentChatCommand(

        /** 会话 ID；首次发起对话可为空，由服务端生成。 */
        String conversationId,

        /** 对话轮次 ID；区分同一会话的多轮对话片段，首次为空时默认 0。 */
        Long iterationId,

        /** 业务上下文：项目 ID。 */
        Long projectId,

        /** 业务上下文：任务 ID。 */
        Long taskId,

        /** 用户提出的问题。 */
        @NotBlank(message = "对话内容不能为空")
        @Size(max = 4000, message = "对话内容长度不能超过 4000")
        String question
) {
}
