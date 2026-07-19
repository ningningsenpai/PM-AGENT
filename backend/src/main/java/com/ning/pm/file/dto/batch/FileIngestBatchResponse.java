package com.ning.pm.file.dto.batch;

import com.ning.pm.file.enums.FileIngestBatchStatus;

import java.time.LocalDateTime;

public record FileIngestBatchResponse(
        Long id,
        Long projectId,
        Integer totalFiles,
        Integer completedFiles,
        Integer succeededFiles,
        Integer failedFiles,
        Integer analysisTotal,
        Integer analysisCompleted,
        Integer analysisSucceeded,
        Integer analysisFailed,
        FileIngestBatchStatus status,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
