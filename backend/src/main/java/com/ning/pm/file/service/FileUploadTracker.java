package com.ning.pm.file.service;

import com.ning.pm.file.domain.ProjectFileUpload;
import com.ning.pm.file.domain.ProjectFileUploadItem;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.FileChangeAction;
import com.ning.pm.file.enums.FileUploadItemStatus;
import com.ning.pm.file.enums.FileUploadSource;
import com.ning.pm.file.enums.FileUploadStatus;
import com.ning.pm.file.repository.ProjectFileUploadItemMapper;
import com.ning.pm.file.repository.ProjectFileUploadMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * FileUploadTracker 记录单文件上传过程，并保留覆盖失败后的修复依据。
 *
 * @author ning
 * @date 2026-07-12
 */
@Component
@RequiredArgsConstructor
public class FileUploadTracker {

    private final ProjectFileUploadMapper uploadMapper;
    private final ProjectFileUploadItemMapper itemMapper;

    /** 创建上传批次；数据库唯一索引负责拦截相同幂等键的并发请求。 */
    public ProjectFileUpload startUpload(
            Long projectId,
            FileBusinessType businessCode,
            FileUploadSource source,
            String idempotencyKey
    ) {
        ProjectFileUpload upload = new ProjectFileUpload();
        upload.setProjectId(projectId);
        upload.setBusinessCode(businessCode);
        upload.setSource(source);
        upload.setStatus(FileUploadStatus.UPLOADING);
        upload.setIdempotencyKey(idempotencyKey);
        upload.setTotalFiles(1);
        upload.setUploadedFiles(0);
        upload.setSkippedFiles(0);
        upload.setFailedFiles(0);
        upload.setStartedAt(LocalDateTime.now());
        try {
            uploadMapper.insert(upload);
        } catch (DuplicateKeyException exception) {
            throw new DuplicateKeyException("相同幂等键的文件请求已经提交", exception);
        }
        return upload;
    }

    public ProjectFileUploadItem startItem(
            Long uploadId,
            Long fileId,
            FileOperationMetadata metadata,
            FileChangeAction action
    ) {
        ProjectFileUploadItem item = new ProjectFileUploadItem();
        item.setUploadId(uploadId);
        item.setFileId(fileId);
        item.setRelativePath(metadata.relativePath());
        item.setQuickFingerprint(metadata.quickFingerprint());
        item.setContentHash(metadata.contentHash());
        item.setSizeBytes(metadata.sizeBytes());
        item.setContentType(metadata.contentType());
        item.setSourceMtimeMs(metadata.sourceMtimeMs());
        item.setAction(action);
        item.setStatus(FileUploadItemStatus.PROCESSING);
        itemMapper.insert(item);
        return item;
    }

    public void complete(ProjectFileUpload upload, ProjectFileUploadItem item, boolean uploaded) {
        item.setStatus(uploaded ? FileUploadItemStatus.SUCCESS : FileUploadItemStatus.SKIPPED);
        item.setErrorMessage(null);
        itemMapper.updateById(item);

        upload.setStatus(FileUploadStatus.COMPLETED);
        upload.setUploadedFiles(uploaded ? 1 : 0);
        upload.setSkippedFiles(uploaded ? 0 : 1);
        upload.setCompletedAt(LocalDateTime.now());
        uploadMapper.updateById(upload);
    }

    public void fail(ProjectFileUpload upload, ProjectFileUploadItem item, String errorMessage) {
        item.setStatus(FileUploadItemStatus.FAILED);
        item.setErrorMessage(limit(errorMessage));
        itemMapper.updateById(item);

        upload.setStatus(FileUploadStatus.FAILED);
        upload.setFailedFiles(1);
        upload.setCompletedAt(LocalDateTime.now());
        uploadMapper.updateById(upload);
    }

    private String limit(String errorMessage) {
        String value = errorMessage == null ? "文件处理失败" : errorMessage;
        return value.length() <= 500 ? value : value.substring(0, 500);
    }
}
