package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.converter.ProjectFileConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.*;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileFingerprintService;
import com.ning.pm.file.service.FileObjectKeyFactory;
import com.ning.pm.file.service.FileOperationMetadata;
import com.ning.pm.file.service.ProjectFileUploadValidator;
import com.ning.pm.file.service.ProjectFileService;
import com.ning.pm.infrastructure.messaging.rabbitmq.publisher.FileEventPublisher;
import com.ning.pm.infrastructure.redis.RedisIdempotencyGuard;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.List;

/**
 * ProjectFileServiceImpl 编排文件元信息、覆盖写状态和MinIO对象操作。
 *
 * @author ning
 * @date 2026-07-12
 */
@Service
@RequiredArgsConstructor
public class ProjectFileServiceImpl implements ProjectFileService {

    private final ProjectFileMapper fileMapper;
    private final ProjectFileConverter fileConverter;
    private final ProjectService projectService;
    private final FileFingerprintService fingerprintService;
    private final ProjectFileUploadValidator fileUploadValidator;
    private final FileObjectKeyFactory objectKeyFactory;
    private final ObjectStorageService objectStorageService;
    private final MinioProperties minioProperties;
    private final RedisIdempotencyGuard idempotencyGuard;
    private final FileEventPublisher fileEventPublisher;



    /** 首次上传先创建文件记录，再按文件ID生成稳定对象键。 */
    @Override
    public ProjectFileResponse createFile(
            Long projectId,
            String idempotencyKey,
            CreateProjectFileRequest request
    ) {
        Project project = projectService.requireOwnedProject(projectId);
        FileOperationMetadata metadata = prepareMetadata(
                request.getRelativePath(),
                request.getSourceMtimeMs(),
                request.getFile()
        );
        ensurePathAvailable(projectId, request.getBusinessCode(), metadata.pathHash(), null);

        String normalizedIdempotencyKey = normalizeIdempotencyKey(idempotencyKey);
        requireIdempotency(
                project.getOwnerUserId(),
                "file:create:" + projectId + ":" + request.getBusinessCode().value(),
                normalizedIdempotencyKey
        );
        ProjectFile file = fileConverter.toEntity(request);
        applyMetadata(file, metadata);
        file.setProjectId(projectId);
        file.setStatus(ProjectFileStatus.UPLOADING);
        file.setLockVersion(0);
        try {
            fileMapper.insert(file);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.FILE_PATH_CONFLICT);
        }
        file.setObjectKey(objectKeyFactory.build(
                project.getOwnerUserId(),
                projectId,
                request.getBusinessCode(),
                file.getId()
        ));
        fileMapper.updateById(file);

        try {
            objectStorageService.putObject(file.getObjectKey(), metadata.content(), metadata.contentType());
            file.setStatus(ProjectFileStatus.ACTIVE);
            fileMapper.updateById(file);
            publishParsingEvent(file);
            return fileConverter.toResponse(file);
        } catch (RuntimeException exception) {
            file.setStatus(ProjectFileStatus.UPLOAD_FAILED);
            fileMapper.updateById(file);
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
            return fileConverter.toResponse(file);
        }

        int claimedVersion = claimForOverwrite(file, request.getLockVersion());
        try {
            objectStorageService.putObject(file.getObjectKey(), metadata.content(), metadata.contentType());
            finalizeOverwrite(file, metadata, claimedVersion);
            return fileConverter.toResponse(file);
        } catch (RuntimeException exception) {
            markVerifyRequired(file.getId(), claimedVersion);
            throw exception;
        }
    }

    /** 路径变化只修改逻辑元信息，不复制或移动MinIO对象。 */
    @Override
    public ProjectFileResponse updatePath(
            Long projectId,
            Long fileId,
            UpdateProjectFilePathRequest request
    ) {
        projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
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
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, fileId)
                .eq(ProjectFile::getProjectId, projectId)
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getLockVersion, request.lockVersion())
                .set(ProjectFile::getRelativePath, relativePath)
                .set(ProjectFile::getPathHash, pathHash)
                .set(ProjectFile::getFileName, fileName)
                .set(ProjectFile::getExtension, fingerprintService.extension(fileName))
                .set(ProjectFile::getSourceMtimeMs, request.sourceMtimeMs())
                .set(ProjectFile::getQuickFingerprint, quickFingerprint)
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
        file.setLockVersion(request.lockVersion() + 1);
        return fileConverter.toResponse(file);
    }

    @Override
    public List<ProjectFileResponse> listFiles(Long projectId, FileBusinessType businessCode) {
        projectService.requireOwnedProject(projectId);
        return fileMapper.selectList(new LambdaQueryWrapper<ProjectFile>()
                        .eq(ProjectFile::getProjectId, projectId)
                        .eq(businessCode != null, ProjectFile::getBusinessCode, businessCode)
                        .orderByAsc(ProjectFile::getRelativePath))
                .stream()
                .map(fileConverter::toResponse)
                .toList();
    }

    @Override
    public FileReadUrlResponse createReadUrl(Long projectId, Long fileId) {
        projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        if (file.getStatus() != ProjectFileStatus.ACTIVE) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID);
        }
        return new FileReadUrlResponse(
                file.getId(),
                file.getFileName(),
                objectStorageService.createReadUrl(file.getObjectKey()),
                LocalDateTime.now().plusSeconds(minioProperties.getReadUrlExpirySeconds())
        );
    }

    @Override
    public void deleteFile(Long projectId, Long fileId, Integer lockVersion) {
        projectService.requireOwnedProject(projectId);
        ProjectFile file = requireFile(projectId, fileId);
        requireActiveAndVersion(file, lockVersion);
        int claimedVersion = claimForDelete(file, lockVersion);
        try {
            objectStorageService.removeObject(file.getObjectKey());
            int deleted = fileMapper.delete(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getId, fileId)
                    .eq(ProjectFile::getStatus, ProjectFileStatus.DELETING)
                    .eq(ProjectFile::getLockVersion, claimedVersion));
            if (deleted == 0) {
                throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件删除状态落库失败");
            }
        } catch (RuntimeException exception) {
            fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                    .eq(ProjectFile::getId, fileId)
                    .eq(ProjectFile::getLockVersion, claimedVersion)
                    .set(ProjectFile::getStatus, ProjectFileStatus.DELETE_FAILED));
            throw exception;
        }
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
                .set(ProjectFile::getStatus, ProjectFileStatus.ACTIVE));
        if (updated == 0) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件覆盖结果落库失败");
        }
        applyMetadata(file, metadata);
        file.setStatus(ProjectFileStatus.ACTIVE);
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

    }
}
