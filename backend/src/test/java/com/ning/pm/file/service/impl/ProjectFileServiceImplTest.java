package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.ning.pm.file.converter.ProjectFileConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.domain.ProjectFileUpload;
import com.ning.pm.file.domain.ProjectFileUploadItem;
import com.ning.pm.file.dto.CreateProjectFileRequest;
import com.ning.pm.file.dto.OverwriteProjectFileRequest;
import com.ning.pm.file.dto.ProjectFileResponse;
import com.ning.pm.file.dto.UpdateProjectFilePathRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.FileUploadSource;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileFingerprintService;
import com.ning.pm.file.service.FileObjectKeyFactory;
import com.ning.pm.file.service.FileUploadTracker;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * ProjectFileServiceImplTest 验证稳定对象键、直接覆盖和路径独立性。
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
    private FileObjectKeyFactory objectKeyFactory = new FileObjectKeyFactory();
    @Mock
    private ObjectStorageService objectStorageService;
    @Mock
    private MinioProperties minioProperties;
    @Mock
    private FileUploadTracker uploadTracker;

    @InjectMocks
    private ProjectFileServiceImpl service;

    @BeforeEach
    void setUp() {
        Project project = new Project();
        project.setId(20L);
        project.setOwnerUserId(10L);
        when(projectService.requireOwnedProject(20L)).thenReturn(project);
        when(fileConverter.toResponse(any(ProjectFile.class)))
                .thenAnswer(invocation -> toResponse(invocation.getArgument(0)));
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
        stubTracking();

        ProjectFileResponse response = service.createFile(20L, "create-key", request);

        assertThat(response.id()).isEqualTo(30L);
        verify(objectStorageService).putObject(
                "PM-AGENT/10/20/project/30",
                "first-content".getBytes(StandardCharsets.UTF_8),
                "text/x-java-source"
        );
    }

    @Test
    void overwriteShouldUseExistingObjectKey() {
        stubMaxFileSize();
        ProjectFile existing = existingFile("old-content");
        when(fileMapper.selectOne(any(Wrapper.class))).thenReturn(existing);
        when(fileMapper.update(isNull(), any())).thenReturn(1);
        stubTracking();
        OverwriteProjectFileRequest request = overwriteRequest("new-content", 2000L);

        ProjectFileResponse response = service.overwriteContent(20L, 30L, "overwrite-key", request);

        verify(objectStorageService).putObject(
                "PM-AGENT/10/20/project/30",
                "new-content".getBytes(StandardCharsets.UTF_8),
                "text/x-java-source"
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
        stubTracking();
        OverwriteProjectFileRequest request = overwriteRequest("same-content", 2000L);

        ProjectFileResponse response = service.overwriteContent(20L, 30L, "metadata-key", request);

        verify(objectStorageService, never()).putObject(anyString(), any(byte[].class), anyString());
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
        stubTracking();
        OverwriteProjectFileRequest request = overwriteRequest("same-content", 2000L);

        service.overwriteContent(20L, 30L, "repair-key", request);

        verify(objectStorageService).putObject(
                "PM-AGENT/10/20/project/30",
                "same-content".getBytes(StandardCharsets.UTF_8),
                "text/x-java-source"
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

        verify(objectStorageService, never()).putObject(anyString(), any(byte[].class), anyString());
        verify(objectStorageService, never()).removeObject(anyString());
        assertThat(response.relativePath()).isEqualTo("src/main/App.java");
        assertThat(existing.getObjectKey()).isEqualTo("PM-AGENT/10/20/project/30");
    }

    private void stubTracking() {
        ProjectFileUpload upload = new ProjectFileUpload();
        upload.setId(40L);
        when(uploadTracker.startUpload(any(), any(), any(), anyString())).thenReturn(upload);
        when(uploadTracker.startItem(any(), any(), any(), any())).thenReturn(new ProjectFileUploadItem());
    }

    private void stubMaxFileSize() {
        when(minioProperties.getMaxFileSizeBytes()).thenReturn(50L * 1024 * 1024);
    }

    private CreateProjectFileRequest createRequest(String path, String content, long mtime) {
        CreateProjectFileRequest request = new CreateProjectFileRequest();
        request.setBusinessCode(FileBusinessType.PROJECT);
        request.setRelativePath(path);
        request.setSourceMtimeMs(mtime);
        request.setSource(FileUploadSource.FRONTEND);
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
        request.setSource(FileUploadSource.FRONTEND);
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
        file.setObjectKey("PM-AGENT/10/20/project/30");
        file.setContentType("text/x-java-source");
        file.setSizeBytes((long) bytes.length);
        file.setSourceMtimeMs(1000L);
        file.setQuickFingerprint(fingerprintService.quickFingerprint("src/App.java", bytes.length, 1000L));
        file.setContentHash(fingerprintService.contentHash(bytes));
        file.setStatus(ProjectFileStatus.ACTIVE);
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
