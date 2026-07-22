package com.ning.pm.file.dto.file;

import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;

import java.time.LocalDateTime;

/**
 * ProjectFileResponse 返回文件逻辑路径、当前元信息和内容指纹。
 *
 * @author ning
 * @date 2026-07-12
 */
public record ProjectFileResponse(
        Long id,
        Long projectId,
        FileBusinessType businessCode,
        String relativePath,
        String fileName,
        String storageName,
        String minioPath,
        String extension,
        String contentType,
        Long sizeBytes,
        Long sourceMtimeMs,
        String quickFingerprint,
        String contentHash,
        ProjectFileStatus status,
        ProjectFileUploadStatus uploadStatus,
        Integer parseAttempts,
        Integer lockVersion,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
