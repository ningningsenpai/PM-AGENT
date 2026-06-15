package com.ning.pm.agent.service;

import com.ning.pm.agent.dto.AgentChatCommand;
import com.ning.pm.agent.vo.AgentChatVO;

/**
 * AgentChatService 对外提供 Agent 对话能力。
 *
 * @author ning
 * @date 2026-06-15
 */
public interface AgentChatService {

    /**
     * 发起一轮对话：组装历史 messages，调用 agent-service，落库并返回结果。
     */
    AgentChatVO chat(AgentChatCommand command);
}
