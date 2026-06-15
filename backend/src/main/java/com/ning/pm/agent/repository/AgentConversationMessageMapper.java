package com.ning.pm.agent.repository;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ning.pm.agent.domain.AgentConversationMessage;

import java.util.List;

/**
 * AgentConversationMessageMapper 负责 Agent 对话消息表的数据访问。
 *
 * @author ning
 * @date 2026-06-15
 */
public interface AgentConversationMessageMapper extends BaseMapper<AgentConversationMessage> {

    /**
     * 查询同一会话 + 同一轮次下的全部消息，按 turn_index 升序，用于组装历史 messages。
     */
    default List<AgentConversationMessage> selectByConversationAndIteration(String conversationId, Long iterationId) {
        LambdaQueryWrapper<AgentConversationMessage> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentConversationMessage::getConversationId, conversationId)
                .eq(AgentConversationMessage::getIterationId, iterationId)
                .orderByAsc(AgentConversationMessage::getTurnIndex);
        return selectList(wrapper);
    }

    /**
     * 取当前轮次的下一个 turn_index；没有历史时返回 0。
     */
    default int selectNextTurnIndex(String conversationId, Long iterationId) {
        return selectByConversationAndIteration(conversationId, iterationId).size();
    }
}
