package com.ning.pm.task.domain;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * TaskPriority 定义任务优先级集合。
 *
 * @author ning
 * @date 2026-06-10
 */
public enum TaskPriority {
    P0("p0"),
    P1("p1"),
    P2("p2"),
    P3("p3");

    private static final Set<String> CODES = Arrays.stream(values())
            .map(TaskPriority::getCode)
            .collect(Collectors.toUnmodifiableSet());

    private final String code;

    TaskPriority(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public static boolean isValid(String code) {
        return code != null && CODES.contains(code);
    }
}
