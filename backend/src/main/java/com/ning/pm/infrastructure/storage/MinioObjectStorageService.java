package com.ning.pm.infrastructure.storage;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import io.minio.BucketExistsArgs;
import io.minio.CopyObjectArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.Http.Method;
import io.minio.ListObjectsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import io.minio.Result;
import io.minio.SourceObject;
import io.minio.messages.Item;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;

/**
 * MinioObjectStorageService 封装对象覆盖写、复制、前缀删除和临时只读地址生成。
 *
 * @author ning
 * @date 2026-07-12
 */
@Service
@RequiredArgsConstructor
public class MinioObjectStorageService implements ObjectStorageService {

    private final MinioClient minioClient;
    private final MinioProperties properties;

    /** 使用明确的桶和对象键上传内容；对象已存在时由 MinIO 直接覆盖。 */
    @Override
    public void putObject(StorageLocation location, byte[] content, String contentType) {
        try {
            ensureBucket(location.bucket());
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(location.bucket())
                    .object(location.objectKey())
                    .stream(new ByteArrayInputStream(content), (long) content.length, -1L)
                    .contentType(contentType)
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public void copyObject(StorageLocation source, StorageLocation target) {
        try {
            ensureBucket(target.bucket());
            minioClient.copyObject(CopyObjectArgs.builder()
                    .bucket(target.bucket())
                    .object(target.objectKey())
                    .source(SourceObject.builder()
                            .bucket(source.bucket())
                            .object(source.objectKey())
                            .build())
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public void removeObject(StorageLocation location) {
        try {
            minioClient.removeObject(RemoveObjectArgs.builder()
                    .bucket(location.bucket())
                    .object(location.objectKey())
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public void removeByPrefix(StorageLocation prefix) {
        try {
            if (!bucketExists(prefix.bucket())) {
                return;
            }
            Iterable<Result<Item>> results = minioClient.listObjects(ListObjectsArgs.builder()
                    .bucket(prefix.bucket())
                    .prefix(prefix.objectKey())
                    .recursive(true)
                    .build());
            for (Result<Item> result : results) {
                Item item = result.get();
                minioClient.removeObject(RemoveObjectArgs.builder()
                        .bucket(prefix.bucket())
                        .object(item.objectName())
                        .build());
            }
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public String createReadUrl(StorageLocation location) {
        try {
            return minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(location.bucket())
                    .object(location.objectKey())
                    .expiry(properties.getReadUrlExpirySeconds())
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    private void ensureBucket(String bucket) throws Exception {
        if (bucketExists(bucket)) {
            return;
        }
        minioClient.makeBucket(MakeBucketArgs.builder()
                .bucket(bucket)
                .build());
    }

    private boolean bucketExists(String bucket) throws Exception {
        return minioClient.bucketExists(BucketExistsArgs.builder()
                .bucket(bucket)
                .build());
    }
}
