package com.ning.pm.infrastructure.storage;

/**
 * StorageLocation 明确区分对象存储桶与对象键，避免把完整展示路径误传给 MinIO SDK。
 *
 * @author ning
 * @date 2026-07-15
 */
public record StorageLocation(String bucket, String objectKey) {

    public static final String PROJECT_BUCKET = "pm-agent";

    public StorageLocation {
        if (bucket == null || bucket.isBlank()) {
            throw new IllegalArgumentException("存储桶不能为空");
        }
        if (objectKey == null || objectKey.isBlank()) {
            throw new IllegalArgumentException("对象键不能为空");
        }
    }

    public String fullPath() {
        return bucket + "/" + objectKey;
    }
}
