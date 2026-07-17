package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BaseException;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.analysis.AgentFileAnalysisProperties;
import com.ning.pm.file.analysis.FileDetailTaskPublisher;
import com.ning.pm.file.batch.ProjectFileIngestBatchService;
import com.ning.pm.file.converter.ProjectFileConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.*;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileAnalysisStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileFingerprintService;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.file.service.FileOperationMetadata;
import com.ning.pm.file.service.ProjectFileUploadValidator;
import com.ning.pm.file.service.ProjectFileService;
import com.ning.pm.infrastructure.redis.RedisIdempotencyGuard;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.List;

/**
 * ProjectFileServiceImpl 编排文件元信息、有限重试、对象迁移和项目索引更新。
 *
 * @author ning
 * @date 2026-07-12
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class ProjectFileServiceImpl implements ProjectFileService {

    private static final int MAX_UPLOAD_ATTEMPTS = 3;

    private final ProjectFileMapper fileMapper;
    private final ProjectFileConverter fileConverter;
    private final ProjectService projectService;
    private final FileFingerprintService fingerprintService;
    private final ProjectFileUploadValidator fileUploadValidator;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectStorageService objectStorageService;
    private final MinioProperties minioProperties;
    private final RedisIdempotencyGuard idempotencyGuard;
    private final ProjectIndexService projectIndexService;
    private final AgentFileAnalysisProperties analysisProperties;
    private final FileDetailTaskPublisher fileDetailTaskPublisher;
    private final ProjectFileIngestBatchService ingestBatchService;

    /** 首次上传持久化稳定存储标识，并在累计三次失败后保留失败记录。 */
    @Override
    public ProjectFileResponse createFile(
            Long projectId,
            String idempotencyKey,
            CreateProjectFileRequest request
    ) {
        // 文件信息以及位置初步校验
        Project project = projectService.requireOwnedProject(projectId);
        if (request.getIngestBatchId() != null) {
            ingestBatchService.requireUploadingBatch(projectId, request.getIngestBatchId());
        }
        requirePublicBusiness(request.getBusinessCode());
        FileOperationMetadata metadata = prepareMetadata(
                request.getRelativePath(),
                request.getSourceMtimeMs(),
                request.getFile()
        );
        ensurePathAvailable(projectId, request.getBusinessCode(), metadata.pathHash(), null);

        // 文件上传接口 Redis 幂等判断
        String normalizedIdempotencyKey = normalizeIdempotencyKey(idempotencyKey);
        requireIdempotency(
                project.getOwnerUserId(),
                "file:create:" + projectId + ":" + request.getBusinessCode().value(),
                normalizedIdempotencyKey
        );
        ProjectFile file = fileConverter.toEntity(request);
        applyMetadata(file, metadata);
        file.setProjectId(projectId);
        file.setIngestBatchId(request.getIngestBatchId());
        file.setStorageUuid(locationFactory.createStorageUuid());
        StorageLocation storageLocation = locationFactory.buildRegularFile(
                project.getOwnerUserId(),
                projectId,
                request.getBusinessCode(),
                metadata.fileName(),
                file.getStorageUuid()
        );
        file.setStorageName(locationFactory.buildStorageName(metadata.fileName(), file.getStorageUuid()));
        file.setObjectKey(storageLocation.objectKey());
        file.setMinioPath(locationFactory.relativeObjectPath(
                project.getOwnerUserId(),
                projectId,
                storageLocation.objectKey()
        ));
        file.setStatus(ProjectFileStatus.UPLOADING);
        file.setUploadStatus(ProjectFileUploadStatus.RETRYING);
        file.setAnalysisStatus(ProjectFileAnalysisStatus.PENDING);
        file.setAnalysisVersion(analysisProperties.getAnalysisVersion());
        file.setDetailRef("system/file_details/" + file.getStorageName());
        file.setAnalysisAttempts(0);
        file.setUploadCompletionRecorded(false);
        file.setAnalysisCompletionRecorded(false);
        file.setUploadAttempts(0);
        file.setLockVersion(0);
        try {
            fileMapper.insert(file);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.FILE_PATH_CONFLICT);
        }
        try {
            uploadNewFileWithRetry(file, metadata);
            if (file.getIngestBatchId() == null) {
                publishParsingEvent(file);
                projectIndexService.rebuild(project);
            } else {
                ingestBatchService.recordUploadTerminal(file, true);
            }
            return fileConverter.toResponse(file);
        } catch (RuntimeException exception) {
            if (file.getStatus() == ProjectFileStatus.UPLOAD_FAILED
                    || file.getStatus() == ProjectFileStatus.VERIFY_REQUIRED) {
                if (file.getIngestBatchId() == null) {
                    rebuildIndexPreservingFailure(project, exception);
                } else {
                    try {
                        ingestBatchService.recordUploadTerminal(file, false);
                    } catch (RuntimeException batchException) {
                        exception.addSuppressed(batchException);
                    }
                }
            }
            throw exception;
        }
    }

    /** 内容变化时覆盖同一对象键；覆盖结果不确定时保留待校验状态。 */
    @Override
    public ProjectFileResponse overwriteContent(
            Long projectId,
            Long fileId,
            String idempotencyKey,
            OverwriteProjectFileRequest request
    ) {
        Project project = projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        requirePublicFile(file);
        requireWritableAndVersion(file, request.getLockVersion());
        FileOperationMetadata metadata = prepareMetadata(
                file.getRelativePath(),
                request.getSourceMtimeMs(),
                request.getFile()
        );

        boolean contentOverwriteRequired = file.getStatus() != ProjectFileStatus.ACTIVE
                || !file.getContentHash().equals(metadata.contentHash());
        String normalizedIdempotencyKey = normalizeIdempotencyKey(idempotencyKey);
        requireIdempotency(
                project.getOwnerUserId(),
                "file:content:" + projectId + ":" + fileId,
                normalizedIdempotencyKey
        );
        if (!contentOverwriteRequired) {
            updateMetadataWithoutContent(file, metadata, request.getLockVersion());
            projectIndexService.rebuild(project);
            return fileConverter.toResponse(file);
        }

        int claimedVersion = claimForOverwrite(file, request.getLockVersion());
        RuntimeException lastException = null;
        for (int attempt = 1; attempt <= MAX_UPLOAD_ATTEMPTS; attempt++) {
            markOverwriteAttempt(file, claimedVersion, attempt);
            try {
                objectStorageService.putObject(
                        locationOf(file),
                        metadata.content(),
                        metadata.contentType()
                );
            } catch (RuntimeException exception) {
                lastException = exception;
                ProjectFileStatus failureStatus = attempt < MAX_UPLOAD_ATTEMPTS
                        ? ProjectFileStatus.VERIFY_REQUIRED
                        : ProjectFileStatus.UPLOAD_FAILED;
                markUploadFailure(file, claimedVersion, attempt, failureStatus, exception);
                continue;
            }
            finalizeOverwrite(file, metadata, claimedVersion);
            publishParsingEvent(file);
            projectIndexService.rebuild(project);
            return fileConverter.toResponse(file);
        }
        cleanupExpectedObject(file, lastException);
        SystemException exhausted = new SystemException(
                ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED,
                "文件内容连续三次上传失败",
                lastException
        );
        rebuildIndexPreservingFailure(project, exhausted);
        throw exhausted;
    }

    /** 目录变化只改逻辑元信息；文件名变化时复制新对象并补偿清理。 */
    @Override
    public ProjectFileResponse updatePath(
            Long projectId,
            Long fileId,
            UpdateProjectFilePathRequest request
    ) {
        Project project = projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        requirePublicFile(file);
        requireActiveAndVersion(file, request.lockVersion());
        String relativePath = fingerprintService.normalizeRelativePath(request.relativePath());
        String fileName = fingerprintService.fileName(relativePath);
        fileUploadValidator.validateRelativePath(relativePath);
        fileUploadValidator.validateExtension(fingerprintService.extension(fileName));
        String pathHash = fingerprintService.pathHash(relativePath);
        ensurePathAvailable(projectId, file.getBusinessCode(), pathHash, fileId);

        String quickFingerprint = fingerprintService.quickFingerprint(
                relativePath,
                file.getSizeBytes(),
                request.sourceMtimeMs()
        );
        if (file.getFileName().equals(fileName)) {
            updateLogicalPath(file, relativePath, fileName, pathHash, quickFingerprint, request);
            publishParsingEvent(file);
            projectIndexService.rebuild(project);
            return fileConverter.toResponse(file);
        }

        StorageLocation source = locationOf(file);
        String previousDetailRef = file.getDetailRef();
        StorageLocation target = locationFactory.buildRegularFile(
                project.getOwnerUserId(),
                projectId,
                file.getBusinessCode(),
                fileName,
                file.getStorageUuid()
        );
        String storageName = locationFactory.buildStorageName(fileName, file.getStorageUuid());
        String minioPath = locationFactory.relativeObjectPath(
                project.getOwnerUserId(),
                projectId,
                target.objectKey()
        );
        String detailRef = "system/file_details/" + storageName;
        int claimedVersion = claimForRename(file, request.lockVersion());
        try {
            objectStorageService.copyObject(source, target);
        } catch (RuntimeException exception) {
            restoreActiveAfterRenameFailure(fileId, claimedVersion);
            throw new SystemException(ErrorCode.FILE_RENAME_FAILED, "复制重命名对象失败", exception);
        }

        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, fileId)
                .eq(ProjectFile::getProjectId, projectId)
                .eq(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .set(ProjectFile::getRelativePath, relativePath)
                .set(ProjectFile::getPathHash, pathHash)
                .set(ProjectFile::getFileName, fileName)
                .set(ProjectFile::getExtension, fingerprintService.extension(fileName))
                .set(ProjectFile::getStorageName, storageName)
                .set(ProjectFile::getObjectKey, target.objectKey())
                .set(ProjectFile::getMinioPath, minioPath)
                .set(ProjectFile::getDetailRef, detailRef)
                .set(ProjectFile::getIngestBatchId, null)
                .set(ProjectFile::getUploadCompletionRecorded, false)
                .set(ProjectFile::getAnalysisCompletionRecorded, false)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.PENDING)
                .set(ProjectFile::getAnalysisModule, null)
                .set(ProjectFile::getAnalysisKind, null)
                .set(ProjectFile::getAnalysisLanguage, null)
                .set(ProjectFile::getAnalysisImportance, null)
                .set(ProjectFile::getAnalysisSummary, null)
                .set(ProjectFile::getAnalysisKeywords, null)
                .set(ProjectFile::getSourceMtimeMs, request.sourceMtimeMs())
                .set(ProjectFile::getQuickFingerprint, quickFingerprint)
                .set(ProjectFile::getStatus, ProjectFileStatus.ACTIVE));
        if (updated == 0) {
            compensateRenameTarget(target);
            restoreActiveAfterRenameFailure(fileId, claimedVersion);
            throw new SystemException(ErrorCode.FILE_RENAME_FAILED, "文件重命名结果落库失败");
        }
        file.setRelativePath(relativePath);
        file.setPathHash(pathHash);
        file.setFileName(fileName);
        file.setExtension(fingerprintService.extension(fileName));
        file.setStorageName(storageName);
        file.setObjectKey(target.objectKey());
        file.setMinioPath(minioPath);
        file.setDetailRef(detailRef);
        file.setIngestBatchId(null);
        file.setUploadCompletionRecorded(false);
        file.setAnalysisCompletionRecorded(false);
        file.setAnalysisStatus(ProjectFileAnalysisStatus.PENDING);
        file.setSourceMtimeMs(request.sourceMtimeMs());
        file.setQuickFingerprint(quickFingerprint);
        file.setLockVersion(claimedVersion);
        file.setStatus(ProjectFileStatus.ACTIVE);
        try {
            objectStorageService.removeObject(source);
        } catch (RuntimeException exception) {
            markVerifyRequired(file.getId(), claimedVersion);
            file.setStatus(ProjectFileStatus.VERIFY_REQUIRED);
            SystemException renameException = new SystemException(
                    ErrorCode.FILE_RENAME_FAILED,
                    "新对象已生效，但旧对象清理失败",
                    exception
            );
            rebuildIndexPreservingFailure(project, renameException);
            throw renameException;
        }
        fileDetailTaskPublisher.publish(file, previousDetailRef);
        projectIndexService.rebuild(project);
        return fileConverter.toResponse(file);
    }

    @Override
    public List<ProjectFileResponse> listFiles(Long projectId, FileBusinessType businessCode) {
        projectService.requireOwnedProject(projectId);
        requirePublicBusinessFilter(businessCode);
        return fileMapper.selectList(new LambdaQueryWrapper<ProjectFile>()
                        .eq(ProjectFile::getProjectId, projectId)
                        .eq(businessCode != null, ProjectFile::getBusinessCode, businessCode)
                        .ne(businessCode == null, ProjectFile::getBusinessCode, FileBusinessType.SYSTEM)
                        .orderByAsc(ProjectFile::getRelativePath))
                .stream()
                .map(fileConverter::toResponse)
                .toList();
    }

    @Override
    public FileReadUrlResponse createReadUrl(Long projectId, Long fileId) {
        projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        requirePublicFile(file);
        if (file.getStatus() != ProjectFileStatus.ACTIVE) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID);
        }
        return new FileReadUrlResponse(
                file.getId(),
                file.getFileName(),
                objectStorageService.createReadUrl(locationOf(file)),
                LocalDateTime.now().plusSeconds(minioProperties.getReadUrlExpirySeconds())
        );
    }

    @Override
    public void deleteFile(Long projectId, Long fileId, Integer lockVersion) {
        Project project = projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        requirePublicFile(file);
        requireActiveAndVersion(file, lockVersion);
        int claimedVersion = claimForDelete(file, lockVersion);
        try {
            objectStorageService.removeObject(locationOf(file));
            int deleted = fileMapper.delete(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getId, fileId)
                    .eq(ProjectFile::getStatus, ProjectFileStatus.DELETING)
                    .eq(ProjectFile::getLockVersion, claimedVersion));
            if (deleted == 0) {
                throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件删除状态落库失败");
            }
            projectIndexService.rebuild(project);
        } catch (RuntimeException exception) {
            fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                    .eq(ProjectFile::getId, fileId)
                    .eq(ProjectFile::getLockVersion, claimedVersion)
                    .set(ProjectFile::getStatus, ProjectFileStatus.DELETE_FAILED));
            throw exception;
        }
    }

    private void uploadNewFileWithRetry(ProjectFile file, FileOperationMetadata metadata) {
        RuntimeException lastException = null;
        for (int attempt = 1; attempt <= MAX_UPLOAD_ATTEMPTS; attempt++) {
            file.setStatus(ProjectFileStatus.UPLOADING);
            file.setUploadStatus(ProjectFileUploadStatus.RETRYING);
            file.setUploadAttempts(attempt);
            fileMapper.updateById(file);
            try {
                objectStorageService.putObject(
                        locationOf(file),
                        metadata.content(),
                        metadata.contentType()
                );
                file.setStatus(ProjectFileStatus.ACTIVE);
                file.setUploadStatus(ProjectFileUploadStatus.SUCCESS);
                clearUploadFailure(file);
                fileMapper.updateById(file);
                return;
            } catch (RuntimeException exception) {
                lastException = exception;
                file.setStatus(attempt < MAX_UPLOAD_ATTEMPTS
                        ? ProjectFileStatus.VERIFY_REQUIRED
                        : ProjectFileStatus.UPLOAD_FAILED);
                file.setUploadStatus(attempt < MAX_UPLOAD_ATTEMPTS
                        ? ProjectFileUploadStatus.RETRYING
                        : ProjectFileUploadStatus.FAILED);
                applyUploadFailure(file, attempt, exception);
                fileMapper.updateById(file);
            }
        }
        // 清除上传成功但是因为其他原因返回失败的 MinIo 对象，避免产生孤岛数据，方便后续进行上传重试
        cleanupExpectedObject(file, lastException);
        throw new SystemException(
                ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED,
                "文件连续三次上传失败",
                lastException
        );
    }

    private void updateLogicalPath(
            ProjectFile file,
            String relativePath,
            String fileName,
            String pathHash,
            String quickFingerprint,
            UpdateProjectFilePathRequest request
    ) {
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getProjectId, file.getProjectId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getLockVersion, request.lockVersion())
                .set(ProjectFile::getRelativePath, relativePath)
                .set(ProjectFile::getPathHash, pathHash)
                .set(ProjectFile::getFileName, fileName)
                .set(ProjectFile::getExtension, fingerprintService.extension(fileName))
                .set(ProjectFile::getSourceMtimeMs, request.sourceMtimeMs())
                .set(ProjectFile::getQuickFingerprint, quickFingerprint)
                .set(ProjectFile::getIngestBatchId, null)
                .set(ProjectFile::getUploadCompletionRecorded, false)
                .set(ProjectFile::getAnalysisCompletionRecorded, false)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.PENDING)
                .set(ProjectFile::getAnalysisModule, null)
                .set(ProjectFile::getAnalysisKind, null)
                .set(ProjectFile::getAnalysisLanguage, null)
                .set(ProjectFile::getAnalysisImportance, null)
                .set(ProjectFile::getAnalysisSummary, null)
                .set(ProjectFile::getAnalysisKeywords, null)
                .set(ProjectFile::getLockVersion, request.lockVersion() + 1));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        file.setRelativePath(relativePath);
        file.setPathHash(pathHash);
        file.setFileName(fileName);
        file.setExtension(fingerprintService.extension(fileName));
        file.setSourceMtimeMs(request.sourceMtimeMs());
        file.setQuickFingerprint(quickFingerprint);
        file.setIngestBatchId(null);
        file.setUploadCompletionRecorded(false);
        file.setAnalysisCompletionRecorded(false);
        file.setAnalysisStatus(ProjectFileAnalysisStatus.PENDING);
        file.setLockVersion(request.lockVersion() + 1);
    }

    private int claimForRename(ProjectFile file, int lockVersion) {
        int claimedVersion = lockVersion + 1;
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getLockVersion, lockVersion)
                .set(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .set(ProjectFile::getLockVersion, claimedVersion));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        file.setStatus(ProjectFileStatus.UPDATING);
        file.setLockVersion(claimedVersion);
        return claimedVersion;
    }

    private void restoreActiveAfterRenameFailure(Long fileId, int claimedVersion) {
        fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, fileId)
                .eq(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .set(ProjectFile::getStatus, ProjectFileStatus.ACTIVE));
    }

    private void compensateRenameTarget(StorageLocation target) {
        try {
            objectStorageService.removeObject(target);
        } catch (RuntimeException exception) {
            log.error("文件重命名落库失败后清理新对象失败 objectKey={}", target.objectKey(), exception);
        }
    }

    private void markOverwriteAttempt(ProjectFile file, int claimedVersion, int attempt) {
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .in(ProjectFile::getStatus,
                        ProjectFileStatus.UPDATING,
                        ProjectFileStatus.VERIFY_REQUIRED)
                .set(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .set(ProjectFile::getUploadStatus, ProjectFileUploadStatus.RETRYING)
                .set(ProjectFile::getUploadAttempts, attempt));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        file.setStatus(ProjectFileStatus.UPDATING);
        file.setUploadStatus(ProjectFileUploadStatus.RETRYING);
        file.setUploadAttempts(attempt);
    }

    private void markUploadFailure(
            ProjectFile file,
            int claimedVersion,
            int attempt,
            ProjectFileStatus status,
            RuntimeException exception
    ) {
        LocalDateTime failedAt = LocalDateTime.now();
        String errorCode = errorCode(exception);
        String errorMessage = errorMessage(exception);
        fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .set(ProjectFile::getStatus, status)
                .set(ProjectFile::getUploadStatus, attempt < MAX_UPLOAD_ATTEMPTS
                        ? ProjectFileUploadStatus.RETRYING
                        : ProjectFileUploadStatus.FAILED)
                .set(ProjectFile::getUploadAttempts, attempt)
                .set(ProjectFile::getLastErrorCode, errorCode)
                .set(ProjectFile::getLastErrorMessage, errorMessage)
                .set(ProjectFile::getLastFailedAt, failedAt));
        file.setStatus(status);
        file.setUploadStatus(attempt < MAX_UPLOAD_ATTEMPTS
                ? ProjectFileUploadStatus.RETRYING
                : ProjectFileUploadStatus.FAILED);
        file.setUploadAttempts(attempt);
        file.setLastErrorCode(errorCode);
        file.setLastErrorMessage(errorMessage);
        file.setLastFailedAt(failedAt);
    }

    private void applyUploadFailure(ProjectFile file, int attempt, RuntimeException exception) {
        file.setUploadAttempts(attempt);
        file.setLastErrorCode(errorCode(exception));
        file.setLastErrorMessage(errorMessage(exception));
        file.setLastFailedAt(LocalDateTime.now());
    }

    private void clearUploadFailure(ProjectFile file) {
        file.setLastErrorCode(null);
        file.setLastErrorMessage(null);
        file.setLastFailedAt(null);
    }

    private void cleanupExpectedObject(ProjectFile file, RuntimeException primaryException) {
        try {
            objectStorageService.removeObject(locationOf(file));
        } catch (RuntimeException cleanupException) {
            if (primaryException != null) {
                primaryException.addSuppressed(cleanupException);
            }
            log.error("文件上传最终失败后清理预期对象失败 fileId={} objectKey={}",
                    file.getId(), file.getObjectKey(), cleanupException);
        }
    }

    private void rebuildIndexPreservingFailure(Project project, RuntimeException primaryException) {
        try {
            projectIndexService.rebuild(project);
        } catch (RuntimeException indexException) {
            primaryException.addSuppressed(indexException);
        }
    }

    private StorageLocation locationOf(ProjectFile file) {
        return new StorageLocation(StorageLocation.PROJECT_BUCKET, file.getObjectKey());
    }

    private String errorCode(RuntimeException exception) {
        if (exception instanceof BaseException baseException) {
            return baseException.getErrorCode().name();
        }
        return ErrorCode.SYSTEM_ERROR.name();
    }

    private String errorMessage(RuntimeException exception) {
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            message = "文件存储调用失败";
        }
        return message.length() <= 500 ? message : message.substring(0, 500);
    }

    private void requirePublicBusiness(FileBusinessType businessType) {
        if (businessType == FileBusinessType.SYSTEM) {
            throw new BizException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED);
        }
    }

    private void requirePublicBusinessFilter(FileBusinessType businessType) {
        if (businessType != null) {
            requirePublicBusiness(businessType);
        }
    }

    private void requirePublicFile(ProjectFile file) {
        requirePublicBusiness(file.getBusinessCode());
    }

    /** Redis在两分钟窗口内拒绝同一用户、同一文件操作范围的重复请求。 */
    private void requireIdempotency(Long userId, String operationScope, String idempotencyKey) {
        if (!idempotencyGuard.tryAcquire(userId, operationScope, idempotencyKey)) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "相同文件请求已在2分钟内提交");
        }
    }

    /**
     * 准备元数据
     *
     * @param relativePath  相对路径
     * @param sourceMtimeMs 源mtime ms
     * @param multipartFile 多部分文件
     * @return FileOperationMetadata保存一次上传判定所需的规范化文件元信息。
     */
    private FileOperationMetadata prepareMetadata(
            String relativePath,
            long sourceMtimeMs,
            MultipartFile multipartFile
    ) {
        if (multipartFile == null || multipartFile.isEmpty()) {
            throw new BizException(ErrorCode.PARAM_INVALID, "上传文件不能为空");
        }
        if (multipartFile.getSize() > minioProperties.getMaxFileSizeBytes()) {
            throw new BizException(ErrorCode.FILE_TOO_LARGE);
        }
        String normalizedPath = fingerprintService.normalizeRelativePath(relativePath);
        String fileName = fingerprintService.fileName(normalizedPath);
        String extension = fingerprintService.extension(fileName);
        fileUploadValidator.validateRelativePath(normalizedPath);
        fileUploadValidator.validateExtension(extension);
        try {
            byte[] content = multipartFile.getBytes();
            String contentType = fileUploadValidator.detectAndValidateMimeType(content);
            return new FileOperationMetadata(
                    normalizedPath,
                    fingerprintService.pathHash(normalizedPath),
                    fileName,
                    extension,
                    contentType,
                    content.length,
                    sourceMtimeMs,
                    fingerprintService.quickFingerprint(normalizedPath, content.length, sourceMtimeMs),
                    fingerprintService.contentHash(content),
                    content
            );
        } catch (IOException exception) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, exception);
        }
    }

    private void ensurePathAvailable(
            Long projectId,
            FileBusinessType businessCode,
            String pathHash,
            Long excludedFileId
    ) {
        long count = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getProjectId, projectId)
                .eq(ProjectFile::getBusinessCode, businessCode)
                .eq(ProjectFile::getPathHash, pathHash)
                .ne(excludedFileId != null, ProjectFile::getId, excludedFileId));
        if (count > 0) {
            throw new BizException(ErrorCode.FILE_PATH_CONFLICT);
        }
    }

    private ProjectFile requireFile(Long projectId, Long fileId) {
        ProjectFile file = fileMapper.selectOne(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getId, fileId)
                .eq(ProjectFile::getProjectId, projectId)
                .last("LIMIT 1"));
        if (file == null) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND);
        }
        return file;
    }

    private void requireActiveAndVersion(ProjectFile file, Integer lockVersion) {
        if (file.getStatus() != ProjectFileStatus.ACTIVE) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID);
        }
        if (!file.getLockVersion().equals(lockVersion)) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
    }

    private void requireWritableAndVersion(ProjectFile file, Integer lockVersion) {
        boolean writable = file.getStatus() == ProjectFileStatus.ACTIVE
                || file.getStatus() == ProjectFileStatus.UPLOAD_FAILED
                || file.getStatus() == ProjectFileStatus.VERIFY_REQUIRED;
        if (!writable) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID);
        }
        if (!file.getLockVersion().equals(lockVersion)) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
    }

    private int claimForOverwrite(ProjectFile file, int lockVersion) {
        int claimedVersion = lockVersion + 1;
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .in(ProjectFile::getStatus,
                        ProjectFileStatus.ACTIVE,
                        ProjectFileStatus.UPLOAD_FAILED,
                        ProjectFileStatus.VERIFY_REQUIRED)
                .eq(ProjectFile::getLockVersion, lockVersion)
                .set(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .set(ProjectFile::getLockVersion, claimedVersion));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        file.setStatus(ProjectFileStatus.UPDATING);
        file.setLockVersion(claimedVersion);
        return claimedVersion;
    }

    private void finalizeOverwrite(ProjectFile file, FileOperationMetadata metadata, int claimedVersion) {
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.UPDATING)
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .set(ProjectFile::getContentType, metadata.contentType())
                .set(ProjectFile::getSizeBytes, metadata.sizeBytes())
                .set(ProjectFile::getSourceMtimeMs, metadata.sourceMtimeMs())
                .set(ProjectFile::getQuickFingerprint, metadata.quickFingerprint())
                .set(ProjectFile::getContentHash, metadata.contentHash())
                .set(ProjectFile::getIngestBatchId, null)
                .set(ProjectFile::getUploadCompletionRecorded, false)
                .set(ProjectFile::getAnalysisCompletionRecorded, false)
                .set(ProjectFile::getUploadStatus, ProjectFileUploadStatus.SUCCESS)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.PENDING)
                .set(ProjectFile::getAnalysisVersion, analysisProperties.getAnalysisVersion())
                .set(ProjectFile::getAnalysisModule, null)
                .set(ProjectFile::getAnalysisKind, null)
                .set(ProjectFile::getAnalysisLanguage, null)
                .set(ProjectFile::getAnalysisImportance, null)
                .set(ProjectFile::getAnalysisSummary, null)
                .set(ProjectFile::getAnalysisKeywords, null)
                .set(ProjectFile::getAnalysisErrorCode, null)
                .set(ProjectFile::getAnalysisErrorMessage, null)
                .set(ProjectFile::getLastErrorCode, null)
                .set(ProjectFile::getLastErrorMessage, null)
                .set(ProjectFile::getLastFailedAt, null)
                .set(ProjectFile::getStatus, ProjectFileStatus.ACTIVE));
        if (updated == 0) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件覆盖结果落库失败");
        }
        applyMetadata(file, metadata);
        file.setStatus(ProjectFileStatus.ACTIVE);
        file.setIngestBatchId(null);
        file.setUploadCompletionRecorded(false);
        file.setAnalysisCompletionRecorded(false);
        file.setUploadStatus(ProjectFileUploadStatus.SUCCESS);
        file.setAnalysisStatus(ProjectFileAnalysisStatus.PENDING);
        file.setAnalysisVersion(analysisProperties.getAnalysisVersion());
        clearUploadFailure(file);
    }

    private void markVerifyRequired(Long fileId, int claimedVersion) {
        fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, fileId)
                .eq(ProjectFile::getLockVersion, claimedVersion)
                .set(ProjectFile::getStatus, ProjectFileStatus.VERIFY_REQUIRED));
    }

    private int claimForDelete(ProjectFile file, int lockVersion) {
        int claimedVersion = lockVersion + 1;
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getLockVersion, lockVersion)
                .set(ProjectFile::getStatus, ProjectFileStatus.DELETING)
                .set(ProjectFile::getLockVersion, claimedVersion));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        return claimedVersion;
    }

    private void updateMetadataWithoutContent(
            ProjectFile file,
            FileOperationMetadata metadata,
            int lockVersion
    ) {
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getLockVersion, lockVersion)
                .set(ProjectFile::getContentType, metadata.contentType())
                .set(ProjectFile::getSizeBytes, metadata.sizeBytes())
                .set(ProjectFile::getSourceMtimeMs, metadata.sourceMtimeMs())
                .set(ProjectFile::getQuickFingerprint, metadata.quickFingerprint())
                .set(ProjectFile::getLockVersion, lockVersion + 1));
        if (updated == 0) {
            throw new BizException(ErrorCode.FILE_BUSY);
        }
        file.setContentType(metadata.contentType());
        file.setSizeBytes(metadata.sizeBytes());
        file.setSourceMtimeMs(metadata.sourceMtimeMs());
        file.setQuickFingerprint(metadata.quickFingerprint());
        file.setLockVersion(lockVersion + 1);
    }

    private void applyMetadata(ProjectFile file, FileOperationMetadata metadata) {
        file.setRelativePath(metadata.relativePath());
        file.setPathHash(metadata.pathHash());
        file.setFileName(metadata.fileName());
        file.setExtension(metadata.extension());
        file.setContentType(metadata.contentType());
        file.setSizeBytes(metadata.sizeBytes());
        file.setSourceMtimeMs(metadata.sourceMtimeMs());
        file.setQuickFingerprint(metadata.quickFingerprint());
        file.setContentHash(metadata.contentHash());
    }

    private String normalizeIdempotencyKey(String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank() || idempotencyKey.length() > 64) {
            throw new BizException(ErrorCode.PARAM_INVALID, "X-Idempotency-Key长度必须为1到64个字符");
        }
        return idempotencyKey.trim();
    }


    /**
     * 发布文件解析事件
     *
     * @param file 文件
     */
    private void publishParsingEvent(ProjectFile file) {
        fileDetailTaskPublisher.publish(file);
    }
}
