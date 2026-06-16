package com.ning.pm.agent.config;

import org.springframework.boot.web.client.RestClientCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * AgentRestClientConfig 装配调用 Python Agent 服务的 RestClient。
 *
 * @author ning
 * @date 2026-06-15
 */
@Configuration
public class AgentRestClientConfig {

    /**
     * 构建 Agent 专用 RestClient，统一注入 baseUrl、超时与 JSON Header。
     */
    @Bean("agentRestClient")
    public RestClient agentRestClient(AgentServiceProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getTimeoutMs());
        factory.setReadTimeout(properties.getTimeoutMs());
        return RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader("Accept", MediaType.APPLICATION_JSON_VALUE)
                .build();
    }
}
