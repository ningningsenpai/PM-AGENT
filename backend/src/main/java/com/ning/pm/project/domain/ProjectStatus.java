package com.ning.pm.project.domain;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;

/**
 * ProjectStatus 定义项目基础状态。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum ProjectStatus {

    ACTIVE("active", "启用"),
    DISABLED("disabled", "停用"),
    DELETING("deleting", "删除中"),
    DELETE_FAILED("delete_failed", "删除失败");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }

    @JsonCreator
    public static ProjectStatus fromCode(String code) {
        return Arrays.stream(values())
                .filter(status -> status.code.equalsIgnoreCase(code))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("项目状态不合法：" + code));
    }
}
