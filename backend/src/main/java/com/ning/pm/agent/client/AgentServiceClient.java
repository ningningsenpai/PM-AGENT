package com.ning.pm.agent.client;

import com.ning.pm.agent.client.payload.AgentServiceChatRequest;
import com.ning.pm.agent.client.payload.AgentServiceChatResponse;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.AgentException;
import com.ning.pm.common.trace.TraceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * AgentServiceClient 是调用 Python Agent 服务对话接口的轻量封装。
 *
 * @author ning
 * @date 2026-06-15
 */
@Component
public class AgentServiceClient {

    private static final Logger log = LoggerFactory.getLogger(AgentServiceClient.class);
    private static final String CHAT_PATH = "/api/v1/agent/chat";

    private final RestClient agentRestClient;

    public AgentServiceClient(@Qualifier("agentRestClient") RestClient agentRestClient) {
        this.agentRestClient = agentRestClient;
    }

    /**
     * 调用 agent-service 的非流式对话接口，失败时抛 AgentException。
     */
    public AgentServiceChatResponse chat(AgentServiceChatRequest request) {
        String traceId = TraceContext.getTraceId();
        try {
            AgentServiceChatResponse response = agentRestClient.post()
                    .uri(CHAT_PATH)
                    .header("X-Trace-Id", traceId == null ? "" : traceId)
                    .body(request)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, resp) -> {
                        log.error("调用 Agent 服务失败 status={} traceId={}", resp.getStatusCode(), traceId);
                        throw new AgentException(ErrorCode.AGENT_SERVICE_ERROR, "Agent 服务返回错误状态");
                    })
                    .body(AgentServiceChatResponse.class);
            if (response == null || response.data() == null) {
                throw new AgentException(ErrorCode.AGENT_SERVICE_ERROR, "Agent 服务响应体为空");
            }
            return response;
        } catch (AgentException ex) {
            throw ex;
        } catch (RestClientException ex) {
            log.error("调用 Agent 服务网络异常 traceId={}", traceId, ex);
            throw new AgentException(ErrorCode.AGENT_SERVICE_ERROR, "Agent 服务调用异常: " + ex.getMessage());
        }
    }
}
