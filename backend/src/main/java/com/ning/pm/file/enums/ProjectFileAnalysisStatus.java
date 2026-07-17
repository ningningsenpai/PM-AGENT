package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 单文件详情解析状态。
 */
@Getter
@RequiredArgsConstructor
public enum ProjectFileAnalysisStatus {

    PENDING("pending"),
    PROCESSING("processing"),
    RETRYING("retrying"),
    SUCCESS("success"),
    FAILED("failed");

    @EnumValue
    @JsonValue
    private final String code;
}
