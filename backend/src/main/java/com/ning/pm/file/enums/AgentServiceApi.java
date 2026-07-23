package com.ning.pm.file.enums;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * AgentServiceApi 集中定义 Python Agent 服务对外提供的接口地址。
 *
 * @author ning
 * @date 2026-07-22
 */
@Getter
@RequiredArgsConstructor
public enum AgentServiceApi {

    HEALTH_CHECK("http://localhost:8000/internal/health"),
    AGENT_CHAT("http://localhost:8000/api/v1/agent/chat"),
    PROJECT_FILE_ANALYZE("http://localhost:8000/api/v1/project-files/analyze");

    private final String url;
}
