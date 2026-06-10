package com.ning.pm.task.domain;

/**
 * TaskStatusLogSource 定义任务状态日志来源。
 *
 * @author ning
 * @date 2026-06-10
 */
public enum TaskStatusLogSource {
    MANUAL("manual"),
    SYSTEM("system"),
    AGENT("agent");

    private final String code;

    TaskStatusLogSource(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
