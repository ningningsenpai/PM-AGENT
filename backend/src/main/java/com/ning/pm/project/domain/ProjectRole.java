package com.ning.pm.project.domain;

/**
 * ProjectRole 定义项目成员在第 1 阶段使用的角色值。
 *
 * @author ning
 * @date 2026-06-10
 */
public enum ProjectRole {
    OWNER("owner");

    private final String code;

    ProjectRole(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
