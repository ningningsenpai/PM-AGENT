package com.ning.pm.agent.service.impl;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.agent.client.AgentServiceClient;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest.ConversationContextPayload;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest.ChatMessagePayload;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest.TokenUsagePayload;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest.TokenUsageSummaryPayload;
import com.ning.pm.agent.client.payload.AgentServiceChatRequest.UserContextPayload;
import com.ning.pm.agent.client.payload.AgentServiceChatResponse;
import com.ning.pm.agent.client.payload.AgentServiceChatResponse.ChatData;
import com.ning.pm.agent.domain.AgentConversationMessage;
import com.ning.pm.agent.dto.AgentChatCommand;
import com.ning.pm.agent.repository.AgentConversationMessageMapper;
import com.ning.pm.agent.service.AgentChatService;
import com.ning.pm.agent.vo.AgentChatVO;
import com.ning.pm.agent.vo.TokenUsageVO;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.AgentException;
import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.repository.UserMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * AgentChatServiceImpl 负责组装对话请求、调用 agent-service 并落库。
 *
 * <p>核心约束：
 * <ul>
 *     <li>历史 messages 仅取同一 conversation_id + iteration_id 下的全部记录；</li>
 *     <li>token 累计统计取同一 conversation_id + iteration_id 下已落库的消耗量，
 *         作为本轮迭代消息已经累计消耗的 token 数量参考；</li>
 *     <li>本轮 user + assistant 同条落库，input/output/total token 来自 agent-service usage。</li>
 * </ul>
 *
 * @author ning
 * @date 2026-06-15
 */
@Service
public class AgentChatServiceImpl implements AgentChatService {

    private static final Logger log = LoggerFactory.getLogger(AgentChatServiceImpl.class);

    /** stream/use_tool_demo 为题目要求自定义的固定值。 */
    private static final boolean DEFAULT_STREAM = false;
    private static final boolean DEFAULT_USE_TOOL_DEMO = false;
    /** 默认租户 ID，等用户权限/多租户扩展后再替换。 */
    private static final String DEFAULT_TENANT_ID = "0";

    private final AgentConversationMessageMapper messageMapper;
    private final AgentServiceClient agentServiceClient;
    private final CurrentUserHolder currentUserHolder;
    private final UserMapper userMapper;
    private final ObjectMapper objectMapper;

    public AgentChatServiceImpl(AgentConversationMessageMapper messageMapper,
                                AgentServiceClient agentServiceClient,
                                CurrentUserHolder currentUserHolder,
                                UserMapper userMapper,
                                ObjectMapper objectMapper) {
        this.messageMapper = messageMapper;
        this.agentServiceClient = agentServiceClient;
        this.currentUserHolder = currentUserHolder;
        this.userMapper = userMapper;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentChatVO chat(AgentChatCommand command) {
        // 1. 规整入参：补全 conversation_id / iteration_id
        String conversationId = StringUtils.hasText(command.conversationId())
                ? command.conversationId()
                : UUID.randomUUID().toString().replace("-", "");
        Long iterationId = command.iterationId() == null ? 0L : command.iterationId();

        // 2. 查询同一 conversation + iteration 历史消息，作为组装上下文与累计 token 的数据源
        List<AgentConversationMessage> history = messageMapper
                .selectByConversationAndIteration(conversationId, iterationId);
        int nextTurnIndex = history.size();
        int historyTotalTokens = history.stream()
                .mapToInt(item -> item.getTotalTokens() == null ? 0 : item.getTotalTokens())
                .sum();
        log.info("准备发起 Agent 对话 conversationId={} iterationId={} historyCount={} historyTotalTokens={}",
                conversationId, iterationId, history.size(), historyTotalTokens);

        // 3. 读取当前登录用户身份
        Long userId = currentUserHolder.getUserIdOrNull();
        String userName = resolveUserName(userId);

        // 4. 组装发送给 agent-service 的请求体
        AgentServiceChatRequest request = buildRequest(
                conversationId, iterationId, command, history, userId, userName, historyTotalTokens);

        // 5. 调用 agent-service 非流式对话接口
        AgentServiceChatResponse response = agentServiceClient.chat(request);
        ChatData data = response.data();
        if (data == null || !StringUtils.hasText(data.answer())) {
            throw new AgentException(ErrorCode.AGENT_SERVICE_ERROR, "Agent 服务未返回有效回答");
        }

        // 6. 拼装并落库本轮对话记录
        AgentConversationMessage record = buildRecord(
                conversationId, iterationId, nextTurnIndex, command,
                userId, userName, data, response.traceId());
        messageMapper.insert(record);
        log.info("Agent 对话落库完成 id={} conversationId={} iterationId={} turnIndex={} totalTokens={}",
                record.getId(), conversationId, iterationId, nextTurnIndex, record.getTotalTokens());

        // 7. 装配 VO 返回
        TokenUsageVO usageVO = new TokenUsageVO(
                record.getInputTokens(),
                record.getOutputTokens(),
                record.getTotalTokens());
        return new AgentChatVO(
                conversationId,
                iterationId,
                nextTurnIndex,
                data.answer(),
                data.model(),
                usageVO);
    }

    /** 根据历史记录构建发送给 agent-service 的 messages，并追加最新一条用户输入。 */
    private AgentServiceChatRequest buildRequest(String conversationId,
                                                 Long iterationId,
                                                 AgentChatCommand command,
                                                 List<AgentConversationMessage> history,
                                                 Long userId,
                                                 String userName,
                                                 int historyTotalTokens) {
        List<ChatMessagePayload> messages = new ArrayList<>();
        // 历史记录已按 turn_index 升序，依次拼成 user / assistant 消息
        for (AgentConversationMessage item : history) {
            if (StringUtils.hasText(item.getUserContent())) {
                messages.add(new ChatMessagePayload("user", item.getUserContent(), null));
            }
            if (StringUtils.hasText(item.getAssistantContent())) {
                messages.add(new ChatMessagePayload("assistant", item.getAssistantContent(), null));
            }
        }
        // 本轮新的用户提问必须放在最后一条
        messages.add(new ChatMessagePayload("user", command.question(), null));

        ConversationContextPayload context = new ConversationContextPayload(
                command.projectId(),
                iterationId,
                historyTotalTokens,
                command.taskId());

        UserContextPayload user = new UserContextPayload(
                userId == null ? "0" : String.valueOf(userId),
                DEFAULT_TENANT_ID,
                userName);

        return new AgentServiceChatRequest(
                conversationId,
                messages,
                context,
                user,
                DEFAULT_STREAM,
                DEFAULT_USE_TOOL_DEMO,
                buildTokenUsageRecords(history),
                buildTokenUsageSummary(history));
    }

    /** 把 agent-service 的响应组装成可落库的 AgentConversationMessage。 */
    private AgentConversationMessage buildRecord(String conversationId,
                                                 Long iterationId,
                                                 int turnIndex,
                                                 AgentChatCommand command,
                                                 Long userId,
                                                 String userName,
                                                 ChatData data,
                                                 String traceId) {
        AgentConversationMessage record = new AgentConversationMessage();
        record.setConversationId(conversationId);
        record.setIterationId(iterationId);
        record.setTurnIndex(turnIndex);
        record.setProjectId(command.projectId());
        record.setTaskId(command.taskId());
        record.setUserId(userId);
        record.setUserName(userName);
        record.setUserContent(command.question());
        record.setAssistantContent(data.answer());
        record.setModel(data.model());

        AgentServiceChatResponse.TokenUsage usage = data.usage();
        record.setInputTokens(usage == null || usage.inputTokens() == null ? 0 : usage.inputTokens());
        record.setOutputTokens(usage == null || usage.outputTokens() == null ? 0 : usage.outputTokens());
        record.setTotalTokens(usage == null || usage.totalTokens() == null ? 0 : usage.totalTokens());

        record.setUseToolDemo(DEFAULT_USE_TOOL_DEMO ? 1 : 0);
        record.setStream(DEFAULT_STREAM ? 1 : 0);
        record.setToolCalls(serializeToolCalls(data));
        record.setStatus("success");
        record.setTraceId(StringUtils.hasText(traceId) ? traceId : TraceContext.getTraceId());
        return record;
    }

    private List<TokenUsagePayload> buildTokenUsageRecords(List<AgentConversationMessage> history) {
        List<TokenUsagePayload> records = new ArrayList<>();
        for (AgentConversationMessage item : history) {
            records.add(new TokenUsagePayload(
                    "deepseek",
                    item.getModel(),
                    item.getTurnIndex(),
                    item.getInputTokens(),
                    item.getOutputTokens(),
                    item.getTotalTokens()));
        }
        return records;
    }

    private TokenUsageSummaryPayload buildTokenUsageSummary(List<AgentConversationMessage> history) {
        int totalInputTokens = 0;
        int totalOutputTokens = 0;
        int totalTokens = 0;
        for (AgentConversationMessage item : history) {
            totalInputTokens += item.getInputTokens() == null ? 0 : item.getInputTokens();
            totalOutputTokens += item.getOutputTokens() == null ? 0 : item.getOutputTokens();
            totalTokens += item.getTotalTokens() == null ? 0 : item.getTotalTokens();
        }
        return new TokenUsageSummaryPayload(totalInputTokens, totalOutputTokens, totalTokens, history.size());
    }

    private String serializeToolCalls(ChatData data) {
        if (data.toolCalls() == null || data.toolCalls().isEmpty()) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(data.toolCalls());
        } catch (JsonProcessingException ex) {
            log.warn("序列化工具调用记录失败，忽略写入 toolCalls 字段", ex);
            return null;
        }
    }

    private String resolveUserName(Long userId) {
        if (userId == null) {
            return null;
        }
        User user = userMapper.selectById(userId);
        return user == null ? null : user.getDisplayName();
    }
}
