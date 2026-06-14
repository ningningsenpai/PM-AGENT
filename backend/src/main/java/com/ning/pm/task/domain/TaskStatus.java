package com.ning.pm.task.domain;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * TaskStatus 定义任务状态集合；第 1 阶段允许任意合法状态之间切换。
 *
 * @author ning
 * @date 2026-06-10
 */
public enum TaskStatus {
    PENDING("pending"),
    DEVELOPING("developing"),
    INTEGRATING("integrating"),
    TESTING("testing"),
    DONE("done"),
    CANCELLED("cancelled");

    private static final Set<String> CODES = Arrays.stream(values())
            .map(TaskStatus::getCode)
            .collect(Collectors.toUnmodifiableSet());

    private final String code;

    TaskStatus(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public static boolean isValid(String code) {
        return code != null && CODES.contains(code);
    }
}
