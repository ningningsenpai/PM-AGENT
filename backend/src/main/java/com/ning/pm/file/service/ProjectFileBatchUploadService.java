package com.ning.pm.file.service;

import cn.hutool.crypto.digest.DigestUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BaseException;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.common.validation.IdempotencyKeyValidator;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.domain.ProjectFileIngestBatch;
import com.ning.pm.file.domain.ProjectFileUploadRequest;
import com.ning.pm.file.dto.batch.ProjectFileUploadResponse;
import com.ning.pm.file.dto.batch.ProjectUploadBatchRequest;
import com.ning.pm.file.dto.batch.ProjectUploadManifestRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.FileIngestBatchStatus;
import com.ning.pm.file.enums.ProjectFileAnalysisStatus;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadRequestStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.enums.ProjectUploadExecutionStatus;
import com.ning.pm.file.repository.ProjectFileIngestBatchMapper;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.repository.ProjectFileUploadRequestMapper;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.repository.ProjectMapper;
import com.ning.pm.project.service.ProjectService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

@Service
@Slf4j
public class ProjectFileBatchUploadService {

    private static final int MAX_BATCH_SIZE = 50;
    private static final int MAX_ATTEMPTS = 3;

    private final ProjectService projectService;
    private final ProjectMapper projectMapper;
    private final ProjectFileMapper fileMapper;
    private final ProjectFileIngestBatchMapper batchMapper;
    private final ProjectFileUploadRequestMapper uploadRequestMapper;
    private final FileFingerprintService fingerprintService;
    private final ProjectFileUploadValidator uploadValidator;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectStorageService objectStorageService;
    private final ProjectFileUploadCompletionService completionService;
    private final TransactionTemplate transactionTemplate;
    private final Executor fileUploadExecutor;
    private final Duration processingTimeout;

    public ProjectFileBatchUploadService(
            ProjectService projectService,
            ProjectMapper projectMapper,
            ProjectFileMapper fileMapper,
            ProjectFileIngestBatchMapper batchMapper,
            ProjectFileUploadRequestMapper uploadRequestMapper,
            FileFingerprintService fingerprintService,
            ProjectFileUploadValidator uploadValidator,
            FileStorageLocationFactory locationFactory,
            ObjectStorageService objectStorageService,
            ProjectFileUploadCompletionService completionService,
            TransactionTemplate transactionTemplate,
            @Qualifier("fileUploadExecutor") Executor fileUploadExecutor,
            @Value("${pm-agent.file.upload.processing-timeout:15m}") Duration processingTimeout
    ) {
        this.projectService = projectService;
        this.projectMapper = projectMapper;
        this.fileMapper = fileMapper;
        this.batchMapper = batchMapper;
        this.uploadRequestMapper = uploadRequestMapper;
        this.fingerprintService = fingerprintService;
        this.uploadValidator = uploadValidator;
        this.locationFactory = locationFactory;
        this.objectStorageService = objectStorageService;
        this.completionService = completionService;
        this.transactionTemplate = transactionTemplate;
        this.fileUploadExecutor = fileUploadExecutor;
        this.processingTimeout = processingTimeout;
    }

    public ProjectFileUploadResponse uploadBatch(
            Long projectId,
            String idempotencyKey,
            ProjectUploadManifestRequest manifest,
            ProjectUploadBatchRequest batchRequest,
            List<MultipartFile> files
    ) {
        Project project = projectService.requireOwnedProject(projectId);
        String normalizedIdempotencyKey = IdempotencyKeyValidator.normalize(idempotencyKey);
        validateRequest(project, manifest, batchRequest, files, normalizedIdempotencyKey);

        List<PreparedFile> preparedFiles = prepareFiles(batchRequest, files);
        String manifestHash = createManifestHash(manifest);
        String payloadHash = createBatchPayloadHash(preparedFiles);
        UploadPreparation preparation = Objects.requireNonNull(transactionTemplate.execute(status ->
                prepareDatabase(
                        project,
                        normalizedIdempotencyKey,
                        manifest,
                        batchRequest,
                        preparedFiles,
                        manifestHash,
                        payloadHash
                )
        ));

        if (!preparation.requiresUpload()) {
            ProjectFileUploadResponse response = buildExistingResponse(
                    preparation.uploadRequest(),
                    preparation.batch(),
                    preparedFiles
            );
            handleCompletionIfNeeded(project, preparation.uploadRequest());
            return response;
        }

        List<CompletableFuture<FileUploadResult>> tasks = preparation.files().stream()
                .map(preparedFile -> CompletableFuture.supplyAsync(
                        () -> uploadOne(project, preparation, preparedFile),
                        fileUploadExecutor
                ))
                .toList();
        List<FileUploadResult> results = tasks.stream()
                .map(CompletableFuture::join)
                .toList();

        BatchFinishResult finishResult = Objects.requireNonNull(transactionTemplate.execute(status ->
                finishBatch(preparation, results)
        ));
        if (finishResult.terminalNow()) {
            completionService.handleCompleted(project, finishResult.uploadRequest().getId());
        }
        return toResponse(finishResult.uploadRequest(), finishResult.batch(), results);
    }

    private UploadPreparation prepareDatabase(
            Project project,
            String idempotencyKey,
            ProjectUploadManifestRequest manifest,
            ProjectUploadBatchRequest batchRequest,
            List<PreparedFile> preparedFiles,
            String manifestHash,
            String payloadHash
    ) {
        lockProject(project);
        ProjectFileUploadRequest uploadRequest = lockUploadRequest(
                project.getId(),
                manifest.requestId().trim()
        );
        if (uploadRequest == null) {
            uploadRequest = createUploadRequest(project, manifest, manifestHash);
            registerRoundBatches(uploadRequest, manifest);
        } else {
            prepareExistingRequest(uploadRequest, manifest, manifestHash);
        }

        ProjectFileIngestBatch batch = requireRoundBatch(
                uploadRequest.getId(),
                manifest.attemptNo(),
                batchRequest.batchId().trim()
        );
        validateRegisteredBatch(batch, batchRequest);
        if (batch.getStatus() == FileIngestBatchStatus.COMPLETED) {
            validateBoundBatchIdentity(batch, idempotencyKey, payloadHash);
            validateCompletedReplay(uploadRequest, batch, preparedFiles);
            return new UploadPreparation(uploadRequest, batch, List.of(), false);
        }
        if (batch.getStatus() == FileIngestBatchStatus.PROCESSING) {
            validateBoundBatchIdentity(batch, idempotencyKey, payloadHash);
            if (!canTakeOver(batch)) {
                throw new BizException(ErrorCode.FILE_BUSY, "该文件批次正在处理中");
            }
            batch.setUpdatedAt(LocalDateTime.now());
            batchMapper.updateById(batch);
        } else if (batch.getStatus() != FileIngestBatchStatus.WAITING) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "该文件批次状态不允许上传");
        }
        if (uploadRequest.getStatus() != ProjectFileUploadRequestStatus.UPLOADING
                || !manifest.attemptNo().equals(uploadRequest.getCurrentAttempt())) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "当前上传请求不接受该轮批次");
        }

        if (batch.getStatus() == FileIngestBatchStatus.WAITING) {
            batch.setIdempotencyKey(idempotencyKey);
            batch.setPayloadHash(payloadHash);
            batch.setStatus(FileIngestBatchStatus.PROCESSING);
            batch.setUpdatedAt(LocalDateTime.now());
            batchMapper.updateById(batch);
        }

        List<PersistedUploadFile> persistedFiles = persistOrLoadFiles(
                project,
                uploadRequest,
                batch,
                manifest.attemptNo(),
                preparedFiles
        );
        return new UploadPreparation(uploadRequest, batch, persistedFiles, true);
    }

    private void prepareExistingRequest(
            ProjectFileUploadRequest uploadRequest,
            ProjectUploadManifestRequest manifest,
            String manifestHash
    ) {
        if (!manifest.originalTotalFiles().equals(uploadRequest.getOriginalTotalFiles())) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "同一请求ID的原始文件总数不一致");
        }
        if (manifest.attemptNo().equals(uploadRequest.getCurrentAttempt())) {
            if (!manifestHash.equals(uploadRequest.getRoundManifestHash())) {
                throw new BizException(ErrorCode.RESOURCE_CONFLICT, "同一上传轮次的批次清单不一致");
            }
            return;
        }
        if (manifest.attemptNo() != uploadRequest.getCurrentAttempt() + 1
                || uploadRequest.getStatus() != ProjectFileUploadRequestStatus.AWAITING_RETRY) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "上传轮次与请求当前状态不一致");
        }
        if (manifest.attemptNo() > MAX_ATTEMPTS) {
            throw new BizException(ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED);
        }
        long pendingFiles = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.NOT_UPLOADED));
        if (pendingFiles != manifest.roundTotalFiles()) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "重试轮次文件数必须等于数据库中的未上传文件数");
        }

        uploadRequest.setCurrentAttempt(manifest.attemptNo());
        uploadRequest.setRoundTotalFiles(manifest.roundTotalFiles());
        uploadRequest.setRoundTotalBatches(manifest.totalBatchCount());
        uploadRequest.setRoundManifestHash(manifestHash);
        uploadRequest.setStatus(ProjectFileUploadRequestStatus.UPLOADING);
        uploadRequest.setFailedFiles(0);
        uploadRequestMapper.updateById(uploadRequest);
        registerRoundBatches(uploadRequest, manifest);
    }

    private ProjectFileUploadRequest createUploadRequest(
            Project project,
            ProjectUploadManifestRequest manifest,
            String manifestHash
    ) {
        if (manifest.attemptNo() != 1
                || manifest.executionStatus() != ProjectUploadExecutionStatus.INITIAL) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "首次提交必须从第1轮初始化上传开始");
        }
        if (!manifest.originalTotalFiles().equals(manifest.roundTotalFiles())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "首次上传的本轮文件数必须等于原始文件总数");
        }
        ProjectFileUploadRequest activeRequest = uploadRequestMapper.selectOne(
                new LambdaQueryWrapper<ProjectFileUploadRequest>()
                        .eq(ProjectFileUploadRequest::getProjectId, project.getId())
                        .in(ProjectFileUploadRequest::getStatus,
                                ProjectFileUploadRequestStatus.UPLOADING,
                                ProjectFileUploadRequestStatus.AWAITING_RETRY)
                        .last("LIMIT 1")
        );
        if (activeRequest != null) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "该项目已有未完成的文件上传请求");
        }

        ProjectFileUploadRequest uploadRequest = new ProjectFileUploadRequest();
        uploadRequest.setOwnerUserId(project.getOwnerUserId());
        uploadRequest.setProjectId(project.getId());
        uploadRequest.setRequestId(manifest.requestId().trim());
        uploadRequest.setOriginalTotalFiles(manifest.originalTotalFiles());
        uploadRequest.setCurrentAttempt(1);
        uploadRequest.setRoundTotalFiles(manifest.roundTotalFiles());
        uploadRequest.setRoundTotalBatches(manifest.totalBatchCount());
        uploadRequest.setRoundManifestHash(manifestHash);
        uploadRequest.setStatus(ProjectFileUploadRequestStatus.UPLOADING);
        uploadRequest.setSucceededFiles(0);
        uploadRequest.setFailedFiles(0);
        try {
            uploadRequestMapper.insert(uploadRequest);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "上传请求ID已存在");
        }
        return uploadRequest;
    }

    private void registerRoundBatches(
            ProjectFileUploadRequest uploadRequest,
            ProjectUploadManifestRequest manifest
    ) {
        for (ProjectUploadManifestRequest.BatchSummary summary : manifest.batches()) {
            ProjectFileIngestBatch batch = new ProjectFileIngestBatch();
            batch.setProjectId(uploadRequest.getProjectId());
            batch.setUploadRequestId(uploadRequest.getId());
            batch.setAttemptNo(manifest.attemptNo());
            batch.setClientBatchId(summary.batchId().trim());
            batch.setTotalFiles(summary.fileCount());
            batch.setCompletedFiles(0);
            batch.setSucceededFiles(0);
            batch.setFailedFiles(0);
            batch.setAnalysisTotal(0);
            batch.setAnalysisCompleted(0);
            batch.setAnalysisSucceeded(0);
            batch.setAnalysisFailed(0);
            batch.setStatus(FileIngestBatchStatus.WAITING);
            batchMapper.insert(batch);
        }
    }

    private List<PersistedUploadFile> persistOrLoadFiles(
            Project project,
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            int attemptNo,
            List<PreparedFile> preparedFiles
    ) {
        List<PersistedUploadFile> result = new ArrayList<>(preparedFiles.size());
        for (PreparedFile prepared : preparedFiles) {
            ProjectFile file = fileMapper.selectOne(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                    .eq(ProjectFile::getClientFileId, prepared.descriptor().clientFileId().trim())
                    .last("LIMIT 1"));
            if (attemptNo == 1) {
                if (file == null) {
                    file = createFileRow(project, uploadRequest, batch, prepared);
                } else {
                    if (!batch.getId().equals(file.getIngestBatchId())) {
                        throw new BizException(
                                ErrorCode.RESOURCE_CONFLICT,
                                "同一文件ID已归属于其他物理批次"
                        );
                    }
                    validateRetryFile(file, prepared);
                }
            } else {
                if (file == null) {
                    throw new BizException(ErrorCode.FILE_NOT_FOUND, "重试文件在数据库中不存在");
                }
                validateRetryFile(file, prepared);
            }
            if (file.getUploadStatus() == ProjectFileUploadStatus.SUCCESS) {
                if (!batch.getId().equals(file.getLastUploadBatchId())) {
                    throw new BizException(
                            ErrorCode.RESOURCE_CONFLICT,
                            "已成功文件不属于当前物理批次"
                    );
                }
                result.add(new PersistedUploadFile(file, prepared, true));
                continue;
            }
            if (file.getUploadStatus() != ProjectFileUploadStatus.NOT_UPLOADED) {
                throw new BizException(ErrorCode.FILE_STATUS_INVALID, "文件上传事实状态不允许继续上传");
            }
            result.add(new PersistedUploadFile(file, prepared, false));
        }
        return result;
    }

    private void validateCompletedReplay(
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            List<PreparedFile> preparedFiles
    ) {
        for (PreparedFile prepared : preparedFiles) {
            ProjectFile file = fileMapper.selectOne(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                    .eq(ProjectFile::getClientFileId, prepared.descriptor().clientFileId().trim())
                    .last("LIMIT 1"));
            if (file == null) {
                throw new BizException(ErrorCode.RESOURCE_CONFLICT, "重放文件在上传请求中不存在");
            }
            validateRetryFile(file, prepared);
            if (file.getUploadStatus() == ProjectFileUploadStatus.SUCCESS) {
                if (!batch.getId().equals(file.getLastUploadBatchId())) {
                    throw new BizException(ErrorCode.RESOURCE_CONFLICT, "成功文件不属于当前物理批次");
                }
            } else if (file.getUploadStatus() != ProjectFileUploadStatus.NOT_UPLOADED) {
                throw new BizException(ErrorCode.RESOURCE_CONFLICT, "重放文件的上传事实状态不合法");
            }
        }
    }

    private ProjectFile createFileRow(
            Project project,
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            PreparedFile prepared
    ) {
        ProjectFile file = new ProjectFile();
        file.setProjectId(project.getId());
        file.setUploadRequestId(uploadRequest.getId());
        file.setClientFileId(prepared.descriptor().clientFileId().trim());
        file.setIngestBatchId(batch.getId());
        file.setBusinessCode(prepared.businessCode());
        file.setRelativePath(prepared.relativePath());
        file.setPathHash(prepared.pathHash());
        file.setFileName(prepared.fileName());
        file.setExtension(prepared.extension());
        file.setContentType(prepared.contentType());
        file.setSizeBytes(prepared.descriptor().sizeBytes());
        file.setSourceMtimeMs(prepared.descriptor().sourceMtimeMs());
        file.setQuickFingerprint(prepared.quickFingerprint());
        file.setContentHash(prepared.contentHash());
        file.setStatus(ProjectFileStatus.UPLOADING);
        file.setUploadStatus(ProjectFileUploadStatus.NOT_UPLOADED);
        file.setAnalysisStatus(ProjectFileAnalysisStatus.PENDING);
        file.setAnalysisAttempts(0);
        file.setUploadCompletionRecorded(false);
        file.setAnalysisCompletionRecorded(false);
        file.setLastUploadAttempt(0);
        file.setUploadAttempts(0);
        file.setLockVersion(0);
        try {
            fileMapper.insert(file);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.FILE_PATH_CONFLICT, "同一项目中已存在相同相对路径的文件");
        }
        return file;
    }

    private FileUploadResult uploadOne(
            Project project,
            UploadPreparation preparation,
            PersistedUploadFile persisted
    ) {
        ProjectFile file = persisted.file();
        PreparedFile prepared = persisted.prepared();
        if (persisted.alreadySucceeded()) {
            return FileUploadResult.succeeded();
        }
        try {
            String storageUuid = locationFactory.createStorageUuid();
            StorageLocation location = locationFactory.buildRegularFile(
                    project.getOwnerUserId(),
                    project.getId(),
                    file.getBusinessCode(),
                    file.getFileName(),
                    storageUuid
            );
            objectStorageService.putObject(location, prepared.content(), prepared.contentType());
            String storageName = locationFactory.buildStorageName(file.getFileName(), storageUuid);
            int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                    .eq(ProjectFile::getId, file.getId())
                    .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.NOT_UPLOADED)
                    .set(ProjectFile::getStorageUuid, storageUuid)
                    .set(ProjectFile::getStorageName, storageName)
                    .set(ProjectFile::getObjectKey, location.objectKey())
                    .set(ProjectFile::getMinioPath, locationFactory.relativeObjectPath(
                            project.getOwnerUserId(),
                            project.getId(),
                            location.objectKey()
                    ))
                    .set(ProjectFile::getDetailRef, "system/file_details/" + storageName)
                    .set(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                    .set(ProjectFile::getUploadStatus, ProjectFileUploadStatus.SUCCESS)
                    .set(ProjectFile::getUploadAttempts, preparation.uploadRequest().getCurrentAttempt())
                    .set(ProjectFile::getLastUploadAttempt, preparation.uploadRequest().getCurrentAttempt())
                    .set(ProjectFile::getLastUploadBatchId, preparation.batch().getId()));
            if (updated != 1) {
                throw new BizException(ErrorCode.FILE_STATUS_INVALID, "文件上传状态已发生变化");
            }
            return FileUploadResult.succeeded();
        } catch (RuntimeException exception) {
            log.warn(
                    "文件上传失败，项目ID：{}，请求ID：{}，轮次：{}，批次ID：{}，文件ID：{}，相对路径：{}",
                    project.getId(),
                    preparation.uploadRequest().getRequestId(),
                    preparation.uploadRequest().getCurrentAttempt(),
                    preparation.batch().getClientBatchId(),
                    prepared.descriptor().clientFileId(),
                    prepared.relativePath(),
                    exception
            );
            return FileUploadResult.failure(toFailedFile(prepared, exception));
        }
    }

    private BatchFinishResult finishBatch(
            UploadPreparation preparation,
            List<FileUploadResult> results
    ) {
        ProjectFileUploadRequest uploadRequest = lockUploadRequestById(preparation.uploadRequest().getId());
        ProjectFileIngestBatch batch = batchMapper.selectOne(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, preparation.batch().getId())
                .last("FOR UPDATE"));
        if (batch == null) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND, "文件上传批次不存在");
        }
        if (batch.getStatus() == FileIngestBatchStatus.COMPLETED) {
            return new BatchFinishResult(uploadRequest, batch, false);
        }

        int succeeded = (int) results.stream().filter(FileUploadResult::success).count();
        int failed = results.size() - succeeded;
        batch.setCompletedFiles(results.size());
        batch.setSucceededFiles(succeeded);
        batch.setFailedFiles(failed);
        batch.setStatus(FileIngestBatchStatus.COMPLETED);
        batchMapper.updateById(batch);

        long registeredBatches = batchMapper.selectCount(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFileIngestBatch::getAttemptNo, uploadRequest.getCurrentAttempt()));
        long completedBatches = batchMapper.selectCount(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFileIngestBatch::getAttemptNo, uploadRequest.getCurrentAttempt())
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.COMPLETED));
        if (registeredBatches != uploadRequest.getRoundTotalBatches()
                || completedBatches != uploadRequest.getRoundTotalBatches()) {
            refreshSuccessCount(uploadRequest);
            return new BatchFinishResult(uploadRequest, batch, false);
        }

        long totalFactFiles = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getUploadRequestId, uploadRequest.getId()));
        long succeededFiles = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.SUCCESS));
        long pendingFiles = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.NOT_UPLOADED));
        if (totalFactFiles != uploadRequest.getOriginalTotalFiles()
                || succeededFiles + pendingFiles != uploadRequest.getOriginalTotalFiles()) {
            throw new BizException(
                    ErrorCode.RESOURCE_CONFLICT,
                    "上传请求的文件事实行数量或状态分布不完整"
            );
        }
        uploadRequest.setSucceededFiles(Math.toIntExact(succeededFiles));
        boolean terminalNow = false;
        if (pendingFiles == 0) {
            uploadRequest.setFailedFiles(0);
            uploadRequest.setStatus(ProjectFileUploadRequestStatus.COMPLETED);
            uploadRequest.setCompletedAt(LocalDateTime.now());
            terminalNow = true;
        } else if (uploadRequest.getCurrentAttempt() < MAX_ATTEMPTS) {
            uploadRequest.setFailedFiles(0);
            uploadRequest.setStatus(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        } else {
            uploadRequest.setFailedFiles(Math.toIntExact(pendingFiles));
            uploadRequest.setStatus(ProjectFileUploadRequestStatus.COMPLETED_WITH_FAILURES);
            uploadRequest.setCompletedAt(LocalDateTime.now());
            terminalNow = true;
        }
        uploadRequestMapper.updateById(uploadRequest);
        return new BatchFinishResult(uploadRequest, batch, terminalNow);
    }

    private void refreshSuccessCount(ProjectFileUploadRequest uploadRequest) {
        long succeededFiles = fileMapper.selectCount(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.SUCCESS));
        uploadRequest.setSucceededFiles(Math.toIntExact(succeededFiles));
        uploadRequestMapper.updateById(uploadRequest);
    }

    private ProjectFileUploadResponse buildExistingResponse(
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            List<PreparedFile> preparedFiles
    ) {
        List<FileUploadResult> reconstructed = preparedFiles.stream()
                .map(prepared -> {
                    ProjectFile file = fileMapper.selectOne(new LambdaQueryWrapper<ProjectFile>()
                            .eq(ProjectFile::getUploadRequestId, uploadRequest.getId())
                            .eq(ProjectFile::getClientFileId, prepared.descriptor().clientFileId().trim())
                            .last("LIMIT 1"));
                    if (file != null && file.getUploadStatus() == ProjectFileUploadStatus.SUCCESS) {
                        return FileUploadResult.succeeded();
                    }
                    return FileUploadResult.failure(new ProjectFileUploadResponse.FailedFile(
                            prepared.descriptor().clientFileId(),
                            prepared.relativePath(),
                            prepared.fileName(),
                            prepared.descriptor().sizeBytes(),
                            prepared.descriptor().sourceMtimeMs(),
                            String.valueOf(ErrorCode.FILE_STORAGE_ERROR.getCode()),
                            "文件尚未上传成功"
                    ));
                })
                .toList();
        return toResponse(uploadRequest, batch, reconstructed);
    }

    private ProjectFileUploadResponse toResponse(
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            List<FileUploadResult> results
    ) {
        List<ProjectFileUploadResponse.FailedFile> failedFiles = results.stream()
                .filter(result -> !result.success())
                .map(FileUploadResult::failedFile)
                .toList();
        int processedFiles = uploadRequest.getSucceededFiles();
        if (uploadRequest.getStatus() == ProjectFileUploadRequestStatus.COMPLETED_WITH_FAILURES) {
            processedFiles += uploadRequest.getFailedFiles();
        }
        return new ProjectFileUploadResponse(
                uploadRequest.getId(),
                uploadRequest.getRequestId(),
                batch.getClientBatchId(),
                batch.getAttemptNo(),
                batch.getStatus(),
                uploadRequest.getStatus(),
                uploadRequest.getOriginalTotalFiles(),
                Math.min(uploadRequest.getOriginalTotalFiles(), processedFiles),
                uploadRequest.getSucceededFiles(),
                batch.getSucceededFiles(),
                batch.getFailedFiles(),
                failedFiles,
                uploadRequest.getStatus() == ProjectFileUploadRequestStatus.AWAITING_RETRY,
                uploadRequest.getStatus() == ProjectFileUploadRequestStatus.COMPLETED_WITH_FAILURES
        );
    }

    private List<PreparedFile> prepareFiles(
            ProjectUploadBatchRequest batchRequest,
            List<MultipartFile> files
    ) {
        List<PreparedFile> result = new ArrayList<>(files.size());
        for (int index = 0; index < files.size(); index++) {
            ProjectUploadBatchRequest.FileDescriptor descriptor = batchRequest.files().get(index);
            MultipartFile multipartFile = files.get(index);
            String relativePath = fingerprintService.normalizeRelativePath(descriptor.relativePath());
            String fileName = fingerprintService.fileName(relativePath);
            if (!fileName.equals(descriptor.fileName())) {
                throw new BizException(ErrorCode.PARAM_INVALID, "文件名必须与相对路径末段一致");
            }
            if (multipartFile.getSize() != descriptor.sizeBytes()) {
                throw new BizException(ErrorCode.PARAM_INVALID, "文件信息中的大小与上传内容不一致");
            }
            FileBusinessType businessCode = descriptor.businessCode() == null
                    ? FileBusinessType.PROJECT
                    : descriptor.businessCode();
            if (businessCode == FileBusinessType.SYSTEM) {
                throw new BizException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED);
            }
            String extension = fingerprintService.extension(fileName);
            uploadValidator.validateRelativePath(relativePath);
            uploadValidator.validateExtension(extension);
            byte[] content;
            try {
                content = multipartFile.getBytes();
            } catch (IOException exception) {
                throw new SystemException(ErrorCode.FILE_STORAGE_ERROR, "读取上传文件失败", exception);
            }
            String contentType = uploadValidator.detectAndValidateMimeType(content);
            result.add(new PreparedFile(
                    descriptor,
                    businessCode,
                    relativePath,
                    fingerprintService.pathHash(relativePath),
                    fileName,
                    extension,
                    contentType,
                    fingerprintService.quickFingerprint(
                            relativePath,
                            descriptor.sizeBytes(),
                            descriptor.sourceMtimeMs()
                    ),
                    fingerprintService.contentHash(content),
                    content
            ));
        }
        return result;
    }

    private void validateRequest(
            Project project,
            ProjectUploadManifestRequest manifest,
            ProjectUploadBatchRequest batch,
            List<MultipartFile> files,
            String idempotencyKey
    ) {
        if (manifest == null || batch == null || files == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "上传清单、批次信息和文件内容不能为空");
        }
        if (!project.getId().equals(manifest.projectId())
                || !project.getId().equals(batch.projectId())
                || !project.getOwnerUserId().equals(manifest.userId())
                || !project.getOwnerUserId().equals(batch.userId())) {
            throw new BizException(ErrorCode.FORBIDDEN, "上传参数不属于当前用户和项目");
        }
        if (!manifest.requestId().trim().equals(batch.requestId().trim())
                || !manifest.attemptNo().equals(batch.attemptNo())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "清单与批次的请求ID或上传轮次不一致");
        }
        if (!idempotencyKey.equals(batch.idempotencyKey().trim())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "请求头与批次对象中的幂等键不一致");
        }
        if (batch.fileCount() > MAX_BATCH_SIZE
                || batch.files().size() != batch.fileCount()
                || files.size() != batch.fileCount()) {
            throw new BizException(ErrorCode.PARAM_INVALID, "单批次最多50个文件，且文件数量必须一致");
        }
        if (manifest.attemptNo() == 1
                && manifest.executionStatus() != ProjectUploadExecutionStatus.INITIAL) {
            throw new BizException(ErrorCode.PARAM_INVALID, "第1轮执行状态必须为initial");
        }
        if (manifest.attemptNo() > 1
                && manifest.executionStatus() != ProjectUploadExecutionStatus.RETRY) {
            throw new BizException(ErrorCode.PARAM_INVALID, "重试轮次执行状态必须为retry");
        }
        if (manifest.batches().size() != manifest.totalBatchCount()) {
            throw new BizException(ErrorCode.PARAM_INVALID, "批次摘要数量与批次总数不一致");
        }
        Set<String> batchIds = new HashSet<>();
        int manifestFileCount = 0;
        Integer currentBatchFileCount = null;
        for (ProjectUploadManifestRequest.BatchSummary summary : manifest.batches()) {
            String batchId = summary.batchId().trim();
            if (!batchIds.add(batchId)) {
                throw new BizException(ErrorCode.PARAM_INVALID, "批次清单中存在重复批次ID");
            }
            manifestFileCount += summary.fileCount();
            if (batchId.equals(batch.batchId().trim())) {
                currentBatchFileCount = summary.fileCount();
            }
        }
        if (manifestFileCount != manifest.roundTotalFiles()
                || currentBatchFileCount == null
                || !currentBatchFileCount.equals(batch.fileCount())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "批次清单中的文件数量不一致");
        }
        Set<String> clientFileIds = new HashSet<>();
        Set<String> relativePaths = new HashSet<>();
        for (ProjectUploadBatchRequest.FileDescriptor descriptor : batch.files()) {
            if (!clientFileIds.add(descriptor.clientFileId().trim())) {
                throw new BizException(ErrorCode.PARAM_INVALID, "批次中存在重复文件ID");
            }
            if (!relativePaths.add(descriptor.relativePath().replace('\\', '/'))) {
                throw new BizException(ErrorCode.PARAM_INVALID, "批次中存在重复相对路径");
            }
        }
    }

    private void validateRegisteredBatch(
            ProjectFileIngestBatch batch,
            ProjectUploadBatchRequest request
    ) {
        if (!batch.getTotalFiles().equals(request.fileCount())) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "批次文件数与预注册清单不一致");
        }
    }

    private void validateBoundBatchIdentity(
            ProjectFileIngestBatch batch,
            String idempotencyKey,
            String payloadHash
    ) {
        if (!Objects.equals(batch.getIdempotencyKey(), idempotencyKey)) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "批次ID已绑定其他幂等键");
        }
        if (!Objects.equals(batch.getPayloadHash(), payloadHash)) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "批次上传载荷与首次提交不一致");
        }
    }

    private void validateRetryFile(ProjectFile file, PreparedFile prepared) {
        if (file.getBusinessCode() != prepared.businessCode()
                || !file.getRelativePath().equals(prepared.relativePath())
                || !file.getFileName().equals(prepared.fileName())
                || !file.getSizeBytes().equals(prepared.descriptor().sizeBytes())
                || !file.getSourceMtimeMs().equals(prepared.descriptor().sourceMtimeMs())
                || !file.getQuickFingerprint().equals(prepared.quickFingerprint())
                || !Objects.equals(file.getContentHash(), prepared.contentHash())) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "重试文件元信息与首次上传不一致");
        }
    }

    private boolean canTakeOver(ProjectFileIngestBatch batch) {
        if (batch.getUpdatedAt() == null) {
            return false;
        }
        return batch.getUpdatedAt().isBefore(LocalDateTime.now().minus(processingTimeout));
    }

    private void lockProject(Project expectedProject) {
        Project lockedProject = projectMapper.selectOne(new LambdaQueryWrapper<Project>()
                .eq(Project::getId, expectedProject.getId())
                .last("FOR UPDATE"));
        if (lockedProject == null
                || !expectedProject.getOwnerUserId().equals(lockedProject.getOwnerUserId())) {
            throw new BizException(ErrorCode.PROJECT_NOT_FOUND);
        }
    }

    private ProjectFileUploadRequest lockUploadRequest(Long projectId, String requestId) {
        return uploadRequestMapper.selectOne(new LambdaQueryWrapper<ProjectFileUploadRequest>()
                .eq(ProjectFileUploadRequest::getProjectId, projectId)
                .eq(ProjectFileUploadRequest::getRequestId, requestId)
                .last("FOR UPDATE"));
    }

    private ProjectFileUploadRequest lockUploadRequestById(Long uploadRequestId) {
        ProjectFileUploadRequest request = uploadRequestMapper.selectOne(
                new LambdaQueryWrapper<ProjectFileUploadRequest>()
                        .eq(ProjectFileUploadRequest::getId, uploadRequestId)
                        .last("FOR UPDATE")
        );
        if (request == null) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND, "文件上传请求不存在");
        }
        return request;
    }

    private ProjectFileIngestBatch requireRoundBatch(
            Long uploadRequestId,
            Integer attemptNo,
            String clientBatchId
    ) {
        ProjectFileIngestBatch batch = batchMapper.selectOne(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getUploadRequestId, uploadRequestId)
                .eq(ProjectFileIngestBatch::getAttemptNo, attemptNo)
                .eq(ProjectFileIngestBatch::getClientBatchId, clientBatchId)
                .last("LIMIT 1"));
        if (batch == null) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND, "批次未在本轮上传清单中注册");
        }
        return batch;
    }

    private void handleCompletionIfNeeded(Project project, ProjectFileUploadRequest uploadRequest) {
        if (uploadRequest.getStatus().isTerminal() && uploadRequest.getIndexRebuiltAt() == null) {
            completionService.handleCompleted(project, uploadRequest.getId());
        }
    }

    private String createManifestHash(ProjectUploadManifestRequest manifest) {
        StringBuilder canonical = new StringBuilder()
                .append(manifest.attemptNo()).append('|')
                .append(manifest.roundTotalFiles()).append('|')
                .append(manifest.totalBatchCount()).append('|');
        manifest.batches().stream()
                .sorted((left, right) -> left.batchId().compareTo(right.batchId()))
                .forEach(summary -> canonical
                        .append(summary.batchId().trim())
                        .append(':')
                        .append(summary.fileCount())
                        .append('|'));
        return DigestUtil.sha256Hex(canonical.toString());
    }

    private String createBatchPayloadHash(List<PreparedFile> preparedFiles) {
        StringBuilder canonical = new StringBuilder();
        appendCanonicalField(canonical, preparedFiles.size());
        preparedFiles.stream()
                .sorted((left, right) -> left.descriptor().clientFileId().trim()
                        .compareTo(right.descriptor().clientFileId().trim()))
                .forEach(prepared -> {
                    appendCanonicalField(canonical, prepared.descriptor().clientFileId().trim());
                    appendCanonicalField(canonical, prepared.businessCode().getCode());
                    appendCanonicalField(canonical, prepared.relativePath());
                    appendCanonicalField(canonical, prepared.fileName());
                    appendCanonicalField(canonical, prepared.descriptor().sizeBytes());
                    appendCanonicalField(canonical, prepared.descriptor().sourceMtimeMs());
                    appendCanonicalField(canonical, prepared.quickFingerprint());
                    appendCanonicalField(canonical, prepared.contentHash());
                });
        return DigestUtil.sha256Hex(canonical.toString());
    }

    private void appendCanonicalField(StringBuilder canonical, Object value) {
        String text = String.valueOf(value);
        canonical.append(text.length()).append(':').append(text);
    }

    private ProjectFileUploadResponse.FailedFile toFailedFile(
            PreparedFile prepared,
            RuntimeException exception
    ) {
        ErrorCode errorCode = exception instanceof BaseException baseException
                ? baseException.getErrorCode()
                : ErrorCode.FILE_STORAGE_ERROR;
        String message = exception.getMessage();
        if (message == null || message.isBlank()) {
            message = errorCode.getMessage();
        }
        return new ProjectFileUploadResponse.FailedFile(
                prepared.descriptor().clientFileId(),
                prepared.relativePath(),
                prepared.fileName(),
                prepared.descriptor().sizeBytes(),
                prepared.descriptor().sourceMtimeMs(),
                String.valueOf(errorCode.getCode()),
                message
        );
    }

    private record PreparedFile(
            ProjectUploadBatchRequest.FileDescriptor descriptor,
            FileBusinessType businessCode,
            String relativePath,
            String pathHash,
            String fileName,
            String extension,
            String contentType,
            String quickFingerprint,
            String contentHash,
            byte[] content
    ) {
    }

    private record PersistedUploadFile(
            ProjectFile file,
            PreparedFile prepared,
            boolean alreadySucceeded
    ) {
    }

    private record UploadPreparation(
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            List<PersistedUploadFile> files,
            boolean requiresUpload
    ) {
    }

    private record FileUploadResult(
            boolean success,
            ProjectFileUploadResponse.FailedFile failedFile
    ) {
        private static FileUploadResult succeeded() {
            return new FileUploadResult(true, null);
        }

        private static FileUploadResult failure(ProjectFileUploadResponse.FailedFile failedFile) {
            return new FileUploadResult(false, failedFile);
        }
    }

    private record BatchFinishResult(
            ProjectFileUploadRequest uploadRequest,
            ProjectFileIngestBatch batch,
            boolean terminalNow
    ) {
    }
}
