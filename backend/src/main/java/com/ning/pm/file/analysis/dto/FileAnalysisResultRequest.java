package com.ning.pm.file.analysis.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

/**
 * Python 回调 Java 的解析结果信封；成功时 detail 必填，失败时携带脱敏错误摘要。
 */
public record FileAnalysisResultRequest(
        @NotBlank @Size(max = 64) String eventId,
        @Positive Long batchId,
        @NotBlank @Size(max = 80) String contentHash,
        @NotBlank @Size(max = 64) String analysisVersion,
        @NotNull FileAnalysisResultStatus status,
        @Valid FileDetailDocument detail,
        @Size(max = 64) String errorCode,
        @Size(max = 500) String errorMessage
) {
}
