package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;

/**
 * FileUploadSource 定义文件上传来源。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum FileUploadSource {

    FRONTEND("frontend", "前端"),
    AGENT("agent", "Agent服务"),
    SYSTEM("system", "系统内部");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }

    @JsonCreator
    public static FileUploadSource fromCode(String code) {
        return Arrays.stream(values())
                .filter(source -> source.code.equalsIgnoreCase(code))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("文件上传来源不合法：" + code));
    }
}
