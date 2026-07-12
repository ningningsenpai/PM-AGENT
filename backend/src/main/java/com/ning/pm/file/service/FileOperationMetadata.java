package com.ning.pm.file.service;

/**
 * FileOperationMetadata 保存一次上传判定所需的规范化文件元信息。
 *
 * @author ning
 * @date 2026-07-12
 */
public record FileOperationMetadata(
        String relativePath,
        String pathHash,
        String fileName,
        String extension,
        String contentType,
        long sizeBytes,
        long sourceMtimeMs,
        String quickFingerprint,
        String contentHash,
        byte[] content
) {
}
