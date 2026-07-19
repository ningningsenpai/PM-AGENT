package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum ProjectFileUploadRequestStatus {

    UPLOADING("uploading"),
    AWAITING_RETRY("awaiting_retry"),
    COMPLETED("completed"),
    COMPLETED_WITH_FAILURES("completed_with_failures");

    @EnumValue
    @JsonValue
    private final String code;

    public boolean isTerminal() {
        return this == COMPLETED || this == COMPLETED_WITH_FAILURES;
    }
}
