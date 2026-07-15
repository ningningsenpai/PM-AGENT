package com.ning.pm.user.domain;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;

/**
 * UserStatus 定义用户账户允许的状态。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum UserStatus {

    ENABLED("enabled", "启用"),
    DISABLED("disabled", "禁用");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }

    @JsonCreator
    public static UserStatus fromCode(String code) {
        return Arrays.stream(values())
                .filter(status -> status.code.equalsIgnoreCase(code))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("用户状态不合法：" + code));
    }
}
