package com.ning.pm.file.analysis;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Getter
@Setter
@ConfigurationProperties(prefix = "pm-agent.agent-service")
public class AgentFileAnalysisProperties {

    private String internalToken = "pm-agent-dev-internal-token";
    private String backendBaseUrl = "http://localhost:8080";
    private String analysisVersion = "file-detail-v1";
}
