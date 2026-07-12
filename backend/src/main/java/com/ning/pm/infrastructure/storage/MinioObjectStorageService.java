package com.ning.pm.infrastructure.storage;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import io.minio.BucketExistsArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.Http.Method;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;

/**
 * MinioObjectStorageService 封装对象覆盖写、删除和临时只读地址生成。
 *
 * @author ning
 * @date 2026-07-12
 */
@Service
@RequiredArgsConstructor
public class MinioObjectStorageService implements ObjectStorageService {

    private final MinioClient minioClient;
    private final MinioProperties properties;

    /** 使用稳定对象键上传内容；对象已存在时由MinIO直接覆盖。 */
    @Override
    public void putObject(String objectKey, byte[] content, String contentType) {
        try {
            ensureBucket();
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .stream(new ByteArrayInputStream(content), (long) content.length, -1L)
                    .contentType(contentType)
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public void removeObject(String objectKey) {
        try {
            minioClient.removeObject(RemoveObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    @Override
    public String createReadUrl(String objectKey) {
        try {
            return minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .expiry(properties.getReadUrlExpirySeconds())
                    .build());
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, exception);
        }
    }

    private void ensureBucket() throws Exception {
        boolean exists = minioClient.bucketExists(BucketExistsArgs.builder()
                .bucket(properties.getBucket())
                .build());
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder()
                    .bucket(properties.getBucket())
                    .build());
        }
    }
}
