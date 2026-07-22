package com.ning.pm.file.dto.parse;

/**
 * FileAnalysisRequest 定义调用 Python 文件分析接口所需的完整元数据。
 *
 * @author ning
 * @date 2026-07-22
 */
public record FileAnalysisRequest(
        Long userId,
        Long projectId,
        String business,
        Long fileId,
        String filename,
        String fileUrl,
        String fileType,
        String storageUuid,
        String storageName,
        String detailRef,
        String originalPath,
        String minioPath,
        Long sizeBytes,
        String contentType,
        String contentHash,
        String analysisVersion
) {
}
