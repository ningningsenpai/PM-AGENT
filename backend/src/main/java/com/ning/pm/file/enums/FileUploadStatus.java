package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * FileUploadStatus 定义上传批次状态。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum FileUploadStatus {

    PENDING("pending", "等待处理"),
    COMPARING("comparing", "差异比较中"),
    UPLOADING("uploading", "上传中"),
    COMPLETED("completed", "已完成"),
    PARTIAL_FAILED("partial_failed", "部分失败"),
    FAILED("failed", "失败");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }
}
