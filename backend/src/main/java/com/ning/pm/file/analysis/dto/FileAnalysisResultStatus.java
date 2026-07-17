package com.ning.pm.file.analysis.dto;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FileAnalysisResultStatus {

    SUCCESS("success"),
    FAILED("failed");

    @JsonValue
    private final String code;
}
