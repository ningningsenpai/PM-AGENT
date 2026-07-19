package com.ning.pm.file.dto.batch;

import com.ning.pm.file.enums.FileIngestBatchStatus;
import com.ning.pm.file.enums.ProjectFileUploadRequestStatus;

import java.util.List;

public record ProjectFileUploadResponse(
        Long uploadRequestId,
        String requestId,
        String batchId,
        Integer attemptNo,
        FileIngestBatchStatus batchStatus,
        ProjectFileUploadRequestStatus requestStatus,
        Integer totalFiles,
        Integer completedFiles,
        Integer succeededFiles,
        Integer batchSucceededFiles,
        Integer batchFailedFiles,
        List<FailedFile> failedFiles,
        boolean requiresRetry,
        boolean requiresProjectUpdate
) {

    public record FailedFile(
            String clientFileId,
            String relativePath,
            String fileName,
            Long sizeBytes,
            Long sourceMtimeMs,
            String errorCode,
            String errorMessage
    ) {
    }
}
