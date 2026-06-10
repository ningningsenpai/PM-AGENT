package com.ning.pm.project.domain;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * ProjectStatus 定义第 1 阶段项目状态集合。
 *
 * @author ning
 * @date 2026-06-10
 */
public enum ProjectStatus {
    NOT_STARTED("not_started"),
    RUNNING("running"),
    PAUSED("paused"),
    DELAYED("delayed"),
    DONE("done"),
    ARCHIVED("archived");

    private static final Set<String> CODES = Arrays.stream(values())
            .map(ProjectStatus::getCode)
            .collect(Collectors.toUnmodifiableSet());

    private final String code;

    ProjectStatus(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public static boolean isValid(String code) {
        return code != null && CODES.contains(code);
    }

    public static boolean cannotCreateTask(String code) {
        return DONE.code.equals(code) || ARCHIVED.code.equals(code);
    }
}
