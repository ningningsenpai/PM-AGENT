package com.ning.pm.file.dto.file;

import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;

public record ProjectFileUploadResponse(
        Long fileId,
        String relativePath,
        String fileName,
        boolean success,
        ProjectFileStatus status,
        ProjectFileUploadStatus uploadStatus,
        String errorCode,
        String errorMessage
) {
}
