package com.ning.pm.file.enums;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum ProjectUploadExecutionStatus {

    INITIAL("initial"),
    RETRY("retry");

    @JsonValue
    private final String code;
}
