package com.ning.pm.agent.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * AgentServiceProperties 承载 Python Agent 服务的连接配置。
 *
 * @author ning
 * @date 2026-06-15
 */
@Getter
@Setter
@Component
@ConfigurationProperties(prefix = "pm.agent-service")
public class AgentServiceProperties {

    /** Agent 服务根地址。 */
    private String baseUrl = "http://localhost:8000";

    /** 单次调用超时时间，单位毫秒。 */
    private int timeoutMs = 60_000;
}
