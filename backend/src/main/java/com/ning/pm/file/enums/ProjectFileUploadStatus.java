package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 文件上传结果独立于文件生命周期状态，仅保留重试中、成功和失败三种业务值。
 */
@Getter
@RequiredArgsConstructor
public enum ProjectFileUploadStatus {

    NOT_UPLOADED("not_uploaded"),
    RETRYING("retrying"),
    SUCCESS("success"),
    FAILED("failed");

    @EnumValue
    @JsonValue
    private final String code;
}
