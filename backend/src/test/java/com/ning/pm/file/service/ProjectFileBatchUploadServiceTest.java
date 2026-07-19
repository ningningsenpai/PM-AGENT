package com.ning.pm.file.service;

import cn.hutool.crypto.digest.DigestUtil;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.domain.ProjectFileIngestBatch;
import com.ning.pm.file.domain.ProjectFileUploadRequest;
import com.ning.pm.file.dto.batch.ProjectFileUploadResponse;
import com.ning.pm.file.dto.batch.ProjectUploadBatchRequest;
import com.ning.pm.file.dto.batch.ProjectUploadManifestRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.FileIngestBatchStatus;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadRequestStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.enums.ProjectUploadExecutionStatus;
import com.ning.pm.file.repository.ProjectFileIngestBatchMapper;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.repository.ProjectFileUploadRequestMapper;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.repository.ProjectMapper;
import com.ning.pm.project.service.ProjectService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProjectFileBatchUploadServiceTest {

    @BeforeAll
    static void initTableInfo() {
        MybatisConfiguration configuration = new MybatisConfiguration();
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "batch-upload-file-test"),
                ProjectFile.class
        );
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "batch-upload-batch-test"),
                ProjectFileIngestBatch.class
        );
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "batch-upload-request-test"),
                ProjectFileUploadRequest.class
        );
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "batch-upload-project-test"),
                Project.class
        );
    }

    @Mock
    private ProjectService projectService;
    @Mock
    private ProjectMapper projectMapper;
    @Mock
    private ProjectFileMapper fileMapper;
    @Mock
    private ProjectFileIngestBatchMapper batchMapper;
    @Mock
    private ProjectFileUploadRequestMapper uploadRequestMapper;
    @Mock
    private ProjectFileUploadValidator uploadValidator;
    @Mock
    private ObjectStorageService objectStorageService;
    @Mock
    private ProjectFileUploadCompletionService completionService;
    @Mock
    private TransactionTemplate transactionTemplate;

    private ProjectFileBatchUploadService service;
    private Project project;
    private AtomicReference<ProjectFileUploadRequest> uploadRequestReference;
    private AtomicReference<ProjectFileIngestBatch> batchReference;
    private AtomicReference<ProjectFile> fileReference;
    private FileFingerprintService fingerprintService;

    @BeforeEach
    void setUp() {
        project = new Project();
        project.setId(10L);
        project.setOwnerUserId(20L);
        project.setProjectName("测试项目");
        when(projectService.requireOwnedProject(10L)).thenReturn(project);
        lenient().when(projectMapper.selectOne(any(Wrapper.class))).thenReturn(project);
        lenient().when(uploadValidator.detectAndValidateMimeType(any())).thenReturn("text/plain");
        executeTransactionsImmediately();

        uploadRequestReference = new AtomicReference<>();
        batchReference = new AtomicReference<>();
        fileReference = new AtomicReference<>();
        fingerprintService = new FileFingerprintService();
        service = new ProjectFileBatchUploadService(
                projectService,
                projectMapper,
                fileMapper,
                batchMapper,
                uploadRequestMapper,
                fingerprintService,
                uploadValidator,
                new FileStorageLocationFactory(),
                objectStorageService,
                completionService,
                transactionTemplate,
                directExecutor(),
                Duration.ofMinutes(15)
        );
    }

    @Test
    void successfulBatchShouldPutOnceAndEnterCompletionCutpoint() {
        preparePersistence(1L, 0L);

        ProjectFileUploadResponse response = service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        );

        assertThat(response.requestStatus()).isEqualTo(ProjectFileUploadRequestStatus.COMPLETED);
        assertThat(response.failedFiles()).isEmpty();
        assertThat(fileReference.get().getUploadStatus()).isEqualTo(ProjectFileUploadStatus.NOT_UPLOADED);
        assertThat(batchReference.get().getUpdatedAt()).isNotNull();
        assertThat(batchReference.get().getPayloadHash()).hasSize(64);
        verify(objectStorageService).putObject(any(), any(), any());
        verify(completionService).handleCompleted(project, 100L);
    }

    @Test
    void failedBatchShouldKeepFileFactAndReturnRetryList() {
        preparePersistence(0L, 1L);
        doThrow(new BizException(ErrorCode.FILE_STORAGE_ERROR))
                .when(objectStorageService).putObject(any(), any(), any());

        ProjectFileUploadResponse response = service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        );

        assertThat(response.requestStatus()).isEqualTo(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        assertThat(response.requiresRetry()).isTrue();
        assertThat(response.failedFiles()).singleElement()
                .extracting(ProjectFileUploadResponse.FailedFile::clientFileId)
                .isEqualTo("file-0");
        assertThat(fileReference.get().getStorageUuid()).isNull();
        assertThat(fileReference.get().getUploadStatus()).isEqualTo(ProjectFileUploadStatus.NOT_UPLOADED);
        verify(objectStorageService).putObject(any(), any(), any());
        verify(fileMapper, never()).update(isNull(), any(Wrapper.class));
        verify(completionService, never()).handleCompleted(any(), any());
    }

    @Test
    void moreThanFiftyFilesShouldBeRejectedBeforeDatabaseMutation() {
        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                manifest(51),
                batch(51),
                multipartFiles(51)
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("最多50个文件");

        verify(uploadRequestMapper, never()).insert(any(ProjectFileUploadRequest.class));
    }

    @Test
    void firstRoundClientFileIdOwnedByAnotherBatchShouldBeRejected() {
        Map<String, ProjectFileIngestBatch> batches = new HashMap<>();
        when(uploadRequestMapper.selectOne(any(Wrapper.class))).thenAnswer(invocation ->
                uploadRequestReference.get());
        doAnswer(invocation -> {
            ProjectFileUploadRequest request = invocation.getArgument(0);
            request.setId(100L);
            uploadRequestReference.set(request);
            return 1;
        }).when(uploadRequestMapper).insert(any(ProjectFileUploadRequest.class));
        doAnswer(invocation -> {
            ProjectFileIngestBatch persistedBatch = invocation.getArgument(0);
            persistedBatch.setId(batches.isEmpty() ? 201L : 202L);
            batches.put(persistedBatch.getClientBatchId(), persistedBatch);
            return 1;
        }).when(batchMapper).insert(any(ProjectFileIngestBatch.class));
        when(batchMapper.selectOne(any(Wrapper.class))).thenAnswer(invocation -> batches.get("batch-2"));
        lenient().when(batchMapper.updateById(any(ProjectFileIngestBatch.class))).thenReturn(1);

        ProjectFile existing = uploadFile("shared-file", 201L, ProjectFileUploadStatus.NOT_UPLOADED);
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);

        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                twoBatchManifest(),
                batchFor("batch-2", "shared-file"),
                multipartFiles(1)
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("其他物理批次");

        verify(objectStorageService, never()).putObject(any(), any(), any());
    }

    @Test
    void sameMetadataButDifferentContentHashShouldBeRejected() {
        ProjectFileUploadRequest request = existingUploadRequest();
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.WAITING);
        ProjectFile existing = uploadFile("file-0", 200L, ProjectFileUploadStatus.NOT_UPLOADED);
        existing.setContentHash(fingerprintService.contentHash("changed".getBytes(StandardCharsets.UTF_8)));
        stubExistingUpload(request, persistedBatch, existing);

        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("元信息与首次上传不一致");

        verify(objectStorageService, never()).putObject(any(), any(), any());
    }

    @Test
    void completionGateShouldRejectIncompleteFileFacts() {
        preparePersistence(1L, 0L);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L, 1L, 0L);

        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("文件事实行数量或状态分布不完整");

        verify(completionService, never()).handleCompleted(any(), any());
    }

    @Test
    void timedOutProcessingBatchShouldReuseItsSuccessfulFileWithoutPuttingAgain() {
        ProjectFileUploadRequest request = existingUploadRequest();
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.PROCESSING);
        persistedBatch.setIdempotencyKey("batch-key");
        persistedBatch.setPayloadHash(payloadHash(batch(1), "abcdef"));
        persistedBatch.setUpdatedAt(LocalDateTime.now().minusMinutes(16));
        ProjectFile existing = uploadFile("file-0", 200L, ProjectFileUploadStatus.SUCCESS);
        existing.setLastUploadBatchId(200L);
        stubExistingUpload(request, persistedBatch, existing);
        when(batchMapper.selectCount(any(Wrapper.class))).thenReturn(1L);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(1L, 1L, 0L);
        lenient().when(uploadRequestMapper.updateById(any(ProjectFileUploadRequest.class))).thenReturn(1);

        ProjectFileUploadResponse response = service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        );

        assertThat(response.requestStatus()).isEqualTo(ProjectFileUploadRequestStatus.COMPLETED);
        assertThat(response.batchSucceededFiles()).isEqualTo(1);
        verify(objectStorageService, never()).putObject(any(), any(), any());
        verify(completionService).handleCompleted(project, 100L);
    }

    @Test
    void completedBatchReplayWithChangedContentShouldBeRejected() {
        ProjectFileUploadRequest request = existingUploadRequest();
        request.setStatus(ProjectFileUploadRequestStatus.COMPLETED);
        request.setIndexRebuiltAt(LocalDateTime.now());
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.COMPLETED);
        persistedBatch.setIdempotencyKey("batch-key");
        persistedBatch.setPayloadHash(payloadHash(batch(1), "abcdef"));
        persistedBatch.setCompletedFiles(1);
        persistedBatch.setSucceededFiles(1);
        ProjectFile existing = uploadFile("file-0", 200L, ProjectFileUploadStatus.SUCCESS);
        existing.setLastUploadBatchId(200L);
        stubExistingUpload(request, persistedBatch, existing);

        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFilesWithContent(1, "ghijkl")
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("批次上传载荷与首次提交不一致");

        verify(objectStorageService, never()).putObject(any(), any(), any());
    }

    @Test
    void completedFailedBatchReplayShouldReturnFailureWithoutPuttingAgain() {
        ProjectFileUploadRequest request = existingUploadRequest();
        request.setStatus(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.COMPLETED);
        persistedBatch.setIdempotencyKey("batch-key");
        persistedBatch.setPayloadHash(payloadHash(batch(1), "abcdef"));
        persistedBatch.setCompletedFiles(1);
        persistedBatch.setFailedFiles(1);
        ProjectFile existing = uploadFile("file-0", 200L, ProjectFileUploadStatus.NOT_UPLOADED);
        stubExistingUpload(request, persistedBatch, existing);

        ProjectFileUploadResponse response = service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        );

        assertThat(response.requestStatus()).isEqualTo(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        assertThat(response.failedFiles()).singleElement()
                .extracting(ProjectFileUploadResponse.FailedFile::clientFileId)
                .isEqualTo("file-0");
        verify(objectStorageService, never()).putObject(any(), any(), any());
    }

    @Test
    void secondAttemptCompletedFailedBatchReplayShouldNotPutOrRewriteFileRow() {
        ProjectFileUploadRequest request = existingUploadRequest();
        request.setCurrentAttempt(2);
        request.setRoundManifestHash(DigestUtil.sha256Hex("2|1|1|batch-1:1|"));
        request.setStatus(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.COMPLETED);
        persistedBatch.setAttemptNo(2);
        persistedBatch.setIdempotencyKey("batch-key");
        persistedBatch.setPayloadHash(payloadHash(retryBatch(1, 2), "abcdef"));
        persistedBatch.setCompletedFiles(1);
        persistedBatch.setFailedFiles(1);
        ProjectFile existing = uploadFile("file-0", 150L, ProjectFileUploadStatus.NOT_UPLOADED);
        stubExistingUpload(request, persistedBatch, existing);

        ProjectFileUploadResponse response = service.uploadBatch(
                10L,
                "batch-key",
                retryManifest(1, 2),
                retryBatch(1, 2),
                multipartFiles(1)
        );

        assertThat(response.requestStatus()).isEqualTo(ProjectFileUploadRequestStatus.AWAITING_RETRY);
        assertThat(response.failedFiles()).singleElement()
                .extracting(ProjectFileUploadResponse.FailedFile::clientFileId)
                .isEqualTo("file-0");
        assertThat(existing.getIngestBatchId()).isEqualTo(150L);
        verify(objectStorageService, never()).putObject(any(), any(), any());
        verify(fileMapper, never()).update(isNull(), any(Wrapper.class));
    }

    @Test
    void completedBatchReplayWithTamperedPayloadHashShouldBeRejected() {
        ProjectFileUploadRequest request = existingUploadRequest();
        request.setStatus(ProjectFileUploadRequestStatus.COMPLETED);
        request.setIndexRebuiltAt(LocalDateTime.now());
        ProjectFileIngestBatch persistedBatch = existingBatch(FileIngestBatchStatus.COMPLETED);
        persistedBatch.setIdempotencyKey("batch-key");
        persistedBatch.setPayloadHash("0".repeat(64));
        persistedBatch.setCompletedFiles(1);
        persistedBatch.setSucceededFiles(1);
        ProjectFile existing = uploadFile("file-0", 200L, ProjectFileUploadStatus.SUCCESS);
        existing.setLastUploadBatchId(200L);
        stubExistingUpload(request, persistedBatch, existing);

        assertThatThrownBy(() -> service.uploadBatch(
                10L,
                "batch-key",
                manifest(1),
                batch(1),
                multipartFiles(1)
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("批次上传载荷与首次提交不一致");

        verify(objectStorageService, never()).putObject(any(), any(), any());
        verify(fileMapper, never()).update(isNull(), any(Wrapper.class));
    }

    private void preparePersistence(long succeededCount, long pendingCount) {
        when(uploadRequestMapper.selectOne(any(Wrapper.class))).thenAnswer(invocation ->
                uploadRequestReference.get());
        doAnswer(invocation -> {
            ProjectFileUploadRequest request = invocation.getArgument(0);
            request.setId(100L);
            uploadRequestReference.set(request);
            return 1;
        }).when(uploadRequestMapper).insert(any(ProjectFileUploadRequest.class));
        lenient().when(uploadRequestMapper.updateById(any(ProjectFileUploadRequest.class)))
                .thenReturn(1);

        doAnswer(invocation -> {
            ProjectFileIngestBatch batch = invocation.getArgument(0);
            batch.setId(200L);
            batchReference.set(batch);
            return 1;
        }).when(batchMapper).insert(any(ProjectFileIngestBatch.class));
        when(batchMapper.selectOne(any(Wrapper.class))).thenAnswer(invocation -> batchReference.get());
        lenient().when(batchMapper.updateById(any(ProjectFileIngestBatch.class))).thenReturn(1);
        when(batchMapper.selectCount(any(Wrapper.class))).thenReturn(1L);

        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(null);
        doAnswer(invocation -> {
            ProjectFile file = invocation.getArgument(0);
            file.setId(300L);
            fileReference.set(file);
            return 1;
        }).when(fileMapper).insert(any(ProjectFile.class));
        lenient().when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(1);
        lenient().when(fileMapper.selectCount(any(Wrapper.class)))
                .thenReturn(1L, succeededCount, pendingCount);
    }

    private void stubExistingUpload(
            ProjectFileUploadRequest request,
            ProjectFileIngestBatch persistedBatch,
            ProjectFile file
    ) {
        uploadRequestReference.set(request);
        batchReference.set(persistedBatch);
        fileReference.set(file);
        when(uploadRequestMapper.selectOne(any(Wrapper.class))).thenReturn(request);
        when(batchMapper.selectOne(any(Wrapper.class))).thenReturn(persistedBatch);
        lenient().when(batchMapper.updateById(any(ProjectFileIngestBatch.class))).thenReturn(1);
        lenient().when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(file);
    }

    private ProjectFileUploadRequest existingUploadRequest() {
        ProjectFileUploadRequest request = new ProjectFileUploadRequest();
        request.setId(100L);
        request.setOwnerUserId(20L);
        request.setProjectId(10L);
        request.setRequestId("request-1");
        request.setOriginalTotalFiles(1);
        request.setCurrentAttempt(1);
        request.setRoundTotalFiles(1);
        request.setRoundTotalBatches(1);
        request.setRoundManifestHash(DigestUtil.sha256Hex("1|1|1|batch-1:1|"));
        request.setStatus(ProjectFileUploadRequestStatus.UPLOADING);
        request.setSucceededFiles(0);
        request.setFailedFiles(0);
        return request;
    }

    private ProjectFileIngestBatch existingBatch(FileIngestBatchStatus status) {
        ProjectFileIngestBatch persistedBatch = new ProjectFileIngestBatch();
        persistedBatch.setId(200L);
        persistedBatch.setProjectId(10L);
        persistedBatch.setUploadRequestId(100L);
        persistedBatch.setAttemptNo(1);
        persistedBatch.setClientBatchId("batch-1");
        persistedBatch.setTotalFiles(1);
        persistedBatch.setCompletedFiles(0);
        persistedBatch.setSucceededFiles(0);
        persistedBatch.setFailedFiles(0);
        persistedBatch.setStatus(status);
        return persistedBatch;
    }

    private ProjectFile uploadFile(
            String clientFileId,
            Long ingestBatchId,
            ProjectFileUploadStatus uploadStatus
    ) {
        byte[] content = "abcdef".getBytes(StandardCharsets.UTF_8);
        ProjectFile file = new ProjectFile();
        file.setId(300L);
        file.setProjectId(10L);
        file.setUploadRequestId(100L);
        file.setClientFileId(clientFileId);
        file.setIngestBatchId(ingestBatchId);
        file.setBusinessCode(FileBusinessType.PROJECT);
        file.setRelativePath("docs/file-0.txt");
        file.setFileName("file-0.txt");
        file.setSizeBytes(6L);
        file.setSourceMtimeMs(1000L);
        file.setQuickFingerprint(fingerprintService.quickFingerprint(
                "docs/file-0.txt",
                6L,
                1000L
        ));
        file.setContentHash(fingerprintService.contentHash(content));
        file.setStatus(uploadStatus == ProjectFileUploadStatus.SUCCESS
                ? ProjectFileStatus.ACTIVE
                : ProjectFileStatus.UPLOADING);
        file.setUploadStatus(uploadStatus);
        return file;
    }

    @SuppressWarnings("unchecked")
    private void executeTransactionsImmediately() {
        lenient().when(transactionTemplate.execute(any())).thenAnswer(invocation -> {
            TransactionCallback<Object> callback = invocation.getArgument(0);
            return callback.doInTransaction((TransactionStatus) null);
        });
    }

    private Executor directExecutor() {
        return Runnable::run;
    }

    private ProjectUploadManifestRequest manifest(int count) {
        return new ProjectUploadManifestRequest(
                20L,
                10L,
                "request-1",
                ProjectUploadExecutionStatus.INITIAL,
                1,
                count,
                count,
                1,
                List.of(new ProjectUploadManifestRequest.BatchSummary("batch-1", count))
        );
    }

    private ProjectUploadBatchRequest batch(int count) {
        return new ProjectUploadBatchRequest(
                20L,
                10L,
                "request-1",
                1,
                "batch-1",
                "batch-key",
                count,
                java.util.stream.IntStream.range(0, count)
                        .mapToObj(index -> new ProjectUploadBatchRequest.FileDescriptor(
                                "file-" + index,
                                FileBusinessType.PROJECT,
                                "docs/file-" + index + ".txt",
                                "file-" + index + ".txt",
                                6L,
                                1000L + index
                        ))
                        .toList()
        );
    }

    private ProjectUploadManifestRequest retryManifest(int count, int attemptNo) {
        return new ProjectUploadManifestRequest(
                20L,
                10L,
                "request-1",
                ProjectUploadExecutionStatus.RETRY,
                attemptNo,
                count,
                count,
                1,
                List.of(new ProjectUploadManifestRequest.BatchSummary("batch-1", count))
        );
    }

    private ProjectUploadBatchRequest retryBatch(int count, int attemptNo) {
        ProjectUploadBatchRequest initial = batch(count);
        return new ProjectUploadBatchRequest(
                initial.userId(),
                initial.projectId(),
                initial.requestId(),
                attemptNo,
                initial.batchId(),
                initial.idempotencyKey(),
                initial.fileCount(),
                initial.files()
        );
    }

    private String payloadHash(ProjectUploadBatchRequest request, String content) {
        StringBuilder canonical = new StringBuilder();
        appendCanonicalField(canonical, request.files().size());
        request.files().stream()
                .sorted((left, right) -> left.clientFileId().trim().compareTo(right.clientFileId().trim()))
                .forEach(descriptor -> {
                    String relativePath = fingerprintService.normalizeRelativePath(descriptor.relativePath());
                    FileBusinessType businessCode = descriptor.businessCode() == null
                            ? FileBusinessType.PROJECT
                            : descriptor.businessCode();
                    appendCanonicalField(canonical, descriptor.clientFileId().trim());
                    appendCanonicalField(canonical, businessCode.getCode());
                    appendCanonicalField(canonical, relativePath);
                    appendCanonicalField(canonical, fingerprintService.fileName(relativePath));
                    appendCanonicalField(canonical, descriptor.sizeBytes());
                    appendCanonicalField(canonical, descriptor.sourceMtimeMs());
                    appendCanonicalField(canonical, fingerprintService.quickFingerprint(
                            relativePath,
                            descriptor.sizeBytes(),
                            descriptor.sourceMtimeMs()
                    ));
                    appendCanonicalField(canonical, fingerprintService.contentHash(
                            content.getBytes(StandardCharsets.UTF_8)
                    ));
                });
        return DigestUtil.sha256Hex(canonical.toString());
    }

    private void appendCanonicalField(StringBuilder canonical, Object value) {
        String text = String.valueOf(value);
        canonical.append(text.length()).append(':').append(text);
    }

    private ProjectUploadManifestRequest twoBatchManifest() {
        return new ProjectUploadManifestRequest(
                20L,
                10L,
                "request-1",
                ProjectUploadExecutionStatus.INITIAL,
                1,
                2,
                2,
                2,
                List.of(
                        new ProjectUploadManifestRequest.BatchSummary("batch-1", 1),
                        new ProjectUploadManifestRequest.BatchSummary("batch-2", 1)
                )
        );
    }

    private ProjectUploadBatchRequest batchFor(String batchId, String clientFileId) {
        return new ProjectUploadBatchRequest(
                20L,
                10L,
                "request-1",
                1,
                batchId,
                "batch-key",
                1,
                List.of(new ProjectUploadBatchRequest.FileDescriptor(
                        clientFileId,
                        FileBusinessType.PROJECT,
                        "docs/file-0.txt",
                        "file-0.txt",
                        6L,
                        1000L
                ))
        );
    }

    private List<MultipartFile> multipartFiles(int count) {
        return multipartFilesWithContent(count, "abcdef");
    }

    private List<MultipartFile> multipartFilesWithContent(int count, String content) {
        return java.util.stream.IntStream.range(0, count)
                .mapToObj(index -> (MultipartFile) new MockMultipartFile(
                        "files",
                        "file-" + index + ".txt",
                        "text/plain",
                        content.getBytes(StandardCharsets.UTF_8)
                ))
                .toList();
    }
}
