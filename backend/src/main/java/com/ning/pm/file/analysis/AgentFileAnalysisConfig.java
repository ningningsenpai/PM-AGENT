package com.ning.pm.file.analysis;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(AgentFileAnalysisProperties.class)
public class AgentFileAnalysisConfig {
}
