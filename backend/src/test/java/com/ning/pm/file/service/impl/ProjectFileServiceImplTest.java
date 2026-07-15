package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.ning.pm.file.converter.ProjectFileConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.CreateProjectFileRequest;
import com.ning.pm.file.dto.OverwriteProjectFileRequest;
import com.ning.pm.file.dto.ProjectFileResponse;
import com.ning.pm.file.dto.UpdateProjectFilePathRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileFingerprintService;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.file.service.ProjectFileUploadValidator;
import com.ning.pm.infrastructure.messaging.rabbitmq.publisher.FileEventPublisher;
import com.ning.pm.infrastructure.redis.RedisIdempotencyGuard;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.times;

/**
 * ProjectFileServiceImplTest 验证稳定存储标识、上传重试和文件重命名迁移。
 *
 * @author ning
 * @date 2026-07-12
 */
@ExtendWith(MockitoExtension.class)
class ProjectFileServiceImplTest {

    @BeforeAll
    static void initTableInfo() {
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(new MybatisConfiguration(), "project-file-test"),
                ProjectFile.class
        );
    }

    @Mock
    private ProjectFileMapper fileMapper;
    @Mock
    private ProjectFileConverter fileConverter;
    @Mock
    private ProjectService projectService;
    @Spy
    private FileFingerprintService fingerprintService = new FileFingerprintService();
    @Spy
    private FileStorageLocationFactory locationFactory = new FileStorageLocationFactory();
    @Mock
    private ProjectFileUploadValidator fileUploadValidator;
    @Mock
    private ObjectStorageService objectStorageService;
    @Mock
    private MinioProperties minioProperties;
    @Mock
    private RedisIdempotencyGuard idempotencyGuard;
    @Mock
    private FileEventPublisher fileEventPublisher;
    @Mock
    private ProjectIndexService projectIndexService;

    @InjectMocks
    private ProjectFileServiceImpl service;

    @BeforeEach
    void setUp() {
        Project project = new Project();
        project.setId(20L);
        project.setOwnerUserId(10L);
        when(projectService.requireOwnedProject(20L)).thenReturn(project);
        lenient().when(fileUploadValidator.detectAndValidateMimeType(any(byte[].class)))
                .thenReturn("text/plain");
        lenient().when(fileConverter.toResponse(any(ProjectFile.class)))
                .thenAnswer(invocation -> toResponse(invocation.getArgument(0)));
        lenient().doReturn("a1b2c3d4e5f67890").when(locationFactory).createStorageUuid();
    }

    @Test
    void createShouldUploadWithStableObjectKey() {
        stubMaxFileSize();
        CreateProjectFileRequest request = createRequest("src/App.java", "first-content", 1000L);
        when(fileConverter.toEntity(request)).thenReturn(new ProjectFile());
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L);
        doAnswer(invocation -> {
            ProjectFile file = invocation.getArgument(0);
            file.setId(30L);
            return 1;
        }).when(fileMapper).insert(any(ProjectFile.class));
        stubIdempotency();

        ProjectFileResponse response = service.createFile(20L, "create-key", request);

        assertThat(response.id()).isEqualTo(30L);
        verify(objectStorageService).putObject(
                new StorageLocation(
                        "pm-agent",
                        "PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java"
                ),
                "first-content".getBytes(StandardCharsets.UTF_8),
                "text/plain"
        );
        verify(projectIndexService).rebuild(any(Project.class));
    }

    @Test
    void duplicateCreateShouldBeRejectedByRedis() {
        stubMaxFileSize();
        CreateProjectFileRequest request = createRequest("src/App.java", "first-content", 1000L);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L);
        when(idempotencyGuard.tryAcquire(
                10L,
                "file:create:20:project",
                "create-key"
        )).thenReturn(false);

        assertThatThrownBy(() -> service.createFile(20L, "create-key", request))
                .isInstanceOf(com.ning.pm.common.exception.BizException.class)
                .hasMessage("相同文件请求已在2分钟内提交");

        verify(objectStorageService, never()).putObject(
                any(StorageLocation.class), any(byte[].class), anyString()
        );
    }

    @Test
    void createShouldRetryThreeTimesAndKeepFailureRecord() {
        stubMaxFileSize();
        CreateProjectFileRequest request = createRequest("src/App.java", "first-content", 1000L);
        ProjectFile file = new ProjectFile();
        when(fileConverter.toEntity(request)).thenReturn(file);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L);
        doAnswer(invocation -> {
            ProjectFile inserted = invocation.getArgument(0);
            inserted.setId(30L);
            return 1;
        }).when(fileMapper).insert(any(ProjectFile.class));
        stubIdempotency();
        doThrow(new SystemException(ErrorCode.FILE_STORAGE_ERROR))
                .when(objectStorageService)
                .putObject(any(StorageLocation.class), any(byte[].class), anyString());

        assertThatThrownBy(() -> service.createFile(20L, "retry-key", request))
                .isInstanceOf(SystemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED);

        verify(objectStorageService, times(3)).putObject(
                any(StorageLocation.class), any(byte[].class), anyString()
        );
        verify(objectStorageService).removeObject(any(StorageLocation.class));
        verify(projectIndexService).rebuild(any(Project.class));
        assertThat(file.getStatus()).isEqualTo(ProjectFileStatus.UPLOAD_FAILED);
        assertThat(file.getUploadAttempts()).isEqualTo(3);
        assertThat(file.getLastErrorCode()).isEqualTo("FILE_STORAGE_ERROR");
    }

    @Test
    void overwriteShouldUseExistingObjectKey() {
        stubMaxFileSize();
        ProjectFile existing = existingFile("old-content");
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.update(isNull(), any())).thenReturn(1);
        stubIdempotency();
        OverwriteProjectFileRequest request = overwriteRequest("new-content", 2000L);

        ProjectFileResponse response = service.overwriteContent(20L, 30L, "overwrite-key", request);

        verify(objectStorageService).putObject(
                new StorageLocation(
                        "pm-agent",
                        "PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java"
                ),
                "new-content".getBytes(StandardCharsets.UTF_8),
                "text/plain"
        );
        assertThat(response.status()).isEqualTo(ProjectFileStatus.ACTIVE);
        assertThat(response.lockVersion()).isEqualTo(1);
    }

    @Test
    void sameContentShouldOnlyUpdateMetadata() {
        stubMaxFileSize();
        ProjectFile existing = existingFile("same-content");
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.update(isNull(), any())).thenReturn(1);
        stubIdempotency();
        OverwriteProjectFileRequest request = overwriteRequest("same-content", 2000L);

        ProjectFileResponse response = service.overwriteContent(20L, 30L, "metadata-key", request);

        verify(objectStorageService, never()).putObject(
                any(StorageLocation.class), any(byte[].class), anyString()
        );
        assertThat(response.sourceMtimeMs()).isEqualTo(2000L);
        assertThat(response.lockVersion()).isEqualTo(1);
    }

    @Test
    void verifyRequiredFileShouldForceOverwriteEvenWhenHashMatches() {
        stubMaxFileSize();
        ProjectFile existing = existingFile("same-content");
        existing.setStatus(ProjectFileStatus.VERIFY_REQUIRED);
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.update(isNull(), any())).thenReturn(1);
        stubIdempotency();
        OverwriteProjectFileRequest request = overwriteRequest("same-content", 2000L);

        service.overwriteContent(20L, 30L, "repair-key", request);

        verify(objectStorageService).putObject(
                new StorageLocation(
                        "pm-agent",
                        "PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java"
                ),
                "same-content".getBytes(StandardCharsets.UTF_8),
                "text/plain"
        );
    }

    @Test
    void pathUpdateShouldNotTouchObjectStorage() {
        ProjectFile existing = existingFile("same-content");
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L);
        when(fileMapper.update(isNull(), any())).thenReturn(1);

        ProjectFileResponse response = service.updatePath(
                20L,
                30L,
                new UpdateProjectFilePathRequest("src/main/App.java", 3000L, 0)
        );

        verify(objectStorageService, never()).putObject(
                any(StorageLocation.class), any(byte[].class), anyString()
        );
        verify(objectStorageService, never()).copyObject(
                any(StorageLocation.class), any(StorageLocation.class)
        );
        verify(objectStorageService, never()).removeObject(any(StorageLocation.class));
        assertThat(response.relativePath()).isEqualTo("src/main/App.java");
        assertThat(existing.getObjectKey())
                .isEqualTo("PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java");
    }

    @Test
    void renameShouldCopyNewObjectAndRemoveOldObject() {
        ProjectFile existing = existingFile("same-content");
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.selectCount(any(Wrapper.class))).thenReturn(0L);
        when(fileMapper.update(isNull(), any())).thenReturn(1);

        ProjectFileResponse response = service.updatePath(
                20L,
                30L,
                new UpdateProjectFilePathRequest("src/Renamed.java", 3000L, 0)
        );

        StorageLocation source = new StorageLocation(
                "pm-agent",
                "PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java"
        );
        StorageLocation target = new StorageLocation(
                "pm-agent",
                "PM-AGENT/10/20/project/Renamed-a1b2c3d4e5f67890.java"
        );
        verify(objectStorageService).copyObject(source, target);
        verify(objectStorageService).removeObject(source);
        assertThat(response.fileName()).isEqualTo("Renamed.java");
        assertThat(existing.getStorageUuid()).isEqualTo("a1b2c3d4e5f67890");
    }

    private void stubIdempotency() {
        when(idempotencyGuard.tryAcquire(any(), anyString(), anyString())).thenReturn(true);
    }

    private void stubMaxFileSize() {
        when(minioProperties.getMaxFileSizeBytes()).thenReturn(50L * 1024 * 1024);
    }

    private CreateProjectFileRequest createRequest(String path, String content, long mtime) {
        CreateProjectFileRequest request = new CreateProjectFileRequest();
        request.setBusinessCode(FileBusinessType.PROJECT);
        request.setRelativePath(path);
        request.setSourceMtimeMs(mtime);
        request.setFile(new MockMultipartFile(
                "file",
                "App.java",
                "text/x-java-source",
                content.getBytes(StandardCharsets.UTF_8)
        ));
        return request;
    }

    private OverwriteProjectFileRequest overwriteRequest(String content, long mtime) {
        OverwriteProjectFileRequest request = new OverwriteProjectFileRequest();
        request.setSourceMtimeMs(mtime);
        request.setLockVersion(0);
        request.setFile(new MockMultipartFile(
                "file",
                "App.java",
                "text/x-java-source",
                content.getBytes(StandardCharsets.UTF_8)
        ));
        return request;
    }

    private ProjectFile existingFile(String content) {
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        ProjectFile file = new ProjectFile();
        file.setId(30L);
        file.setProjectId(20L);
        file.setBusinessCode(FileBusinessType.PROJECT);
        file.setRelativePath("src/App.java");
        file.setPathHash(fingerprintService.pathHash("src/App.java"));
        file.setFileName("App.java");
        file.setExtension("java");
        file.setStorageUuid("a1b2c3d4e5f67890");
        file.setObjectKey("PM-AGENT/10/20/project/App-a1b2c3d4e5f67890.java");
        file.setContentType("text/x-java-source");
        file.setSizeBytes((long) bytes.length);
        file.setSourceMtimeMs(1000L);
        file.setQuickFingerprint(fingerprintService.quickFingerprint("src/App.java", bytes.length, 1000L));
        file.setContentHash(fingerprintService.contentHash(bytes));
        file.setStatus(ProjectFileStatus.ACTIVE);
        file.setUploadAttempts(1);
        file.setLockVersion(0);
        return file;
    }

    private ProjectFileResponse toResponse(ProjectFile file) {
        return new ProjectFileResponse(
                file.getId(),
                file.getProjectId(),
                file.getBusinessCode(),
                file.getRelativePath(),
                file.getFileName(),
                file.getExtension(),
                file.getContentType(),
                file.getSizeBytes(),
                file.getSourceMtimeMs(),
                file.getQuickFingerprint(),
                file.getContentHash(),
                file.getStatus(),
                file.getLockVersion(),
                file.getCreatedAt(),
                file.getUpdatedAt()
        );
    }
}
