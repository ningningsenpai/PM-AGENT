package com.ning.pm.file.batch;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FileIngestBatchStatus {

    UPLOADING("uploading"),
    UPLOAD_COMPLETED("upload_completed"),
    ANALYZING("analyzing"),
    COMPLETED("completed");

    @EnumValue
    @JsonValue
    private final String code;
}
