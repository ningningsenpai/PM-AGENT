package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FileIngestBatchStatus {

    WAITING("waiting"),
    PROCESSING("processing"),
    COMPLETED("completed"),

    /** 历史状态仅用于兼容旧数据，新的批次上传链路不再写入。 */
    UPLOADING("uploading"),
    UPLOAD_COMPLETED("upload_completed"),
    ANALYZING("analyzing");

    @EnumValue
    @JsonValue
    private final String code;
}
