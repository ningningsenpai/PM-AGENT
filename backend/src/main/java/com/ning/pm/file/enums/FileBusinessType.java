package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;

/**
 * FileBusinessType 定义项目内文件命名空间。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum FileBusinessType {

    PROJECT("project", "项目文件"),
    USER("user", "用户资料"),
    SYSTEM("system", "系统产物");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }

    @JsonCreator
    public static FileBusinessType fromCode(String code) {
        return Arrays.stream(values())
                .filter(type -> type.code.equalsIgnoreCase(code))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("文件业务类型不合法：" + code));
    }
}
