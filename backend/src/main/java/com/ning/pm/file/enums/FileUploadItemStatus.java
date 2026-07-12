package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * FileUploadItemStatus 定义上传明细处理状态。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum FileUploadItemStatus {

    PENDING("pending", "等待处理"),
    PROCESSING("processing", "处理中"),
    SKIPPED("skipped", "已跳过"),
    SUCCESS("success", "成功"),
    FAILED("failed", "失败");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }
}
