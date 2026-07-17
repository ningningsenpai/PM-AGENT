package com.ning.pm.file.analysis;

import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.analysis.dto.FileAnalysisResultRequest;
import com.ning.pm.file.analysis.dto.FileAnalysisResultStatus;
import com.ning.pm.file.analysis.dto.FileDetailDocument;
import com.ning.pm.file.batch.ProjectFileIngestBatchService;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.repository.ProjectMapper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class FileDetailAnalysisServiceTest {

    @BeforeAll
    static void initTableInfo() {
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(new MybatisConfiguration(), "file-analysis-test"),
                ProjectFile.class
        );
    }

    @Mock
    private ProjectMapper projectMapper;
    @Mock
    private ProjectFileMapper fileMapper;
    @Mock
    private ObjectStorageService objectStorageService;
    @Mock
    private ProjectIndexService projectIndexService;
    @Mock
    private ProjectFileIngestBatchService ingestBatchService;

    private FileDetailAnalysisService service;
    private Project project;
    private ProjectFile file;

    @BeforeEach
    void setUp() {
        project = new Project();
        project.setId(10L);
        project.setOwnerUserId(1L);
        project.setStatus(ProjectStatus.ACTIVE);
        file = new ProjectFile();
        file.setId(30L);
        file.setProjectId(10L);
        file.setBusinessCode(FileBusinessType.PROJECT);
        file.setRelativePath("backend/README.md");
        file.setFileName("README.md");
        file.setStorageUuid("a1b2c3d4e5f67890");
        file.setStorageName("README-a1b2c3d4e5f67890.md");
        file.setObjectKey("PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md");
        file.setMinioPath("project/README-a1b2c3d4e5f67890.md");
        file.setDetailRef("system/file_details/README-a1b2c3d4e5f67890.md");
        file.setContentHash("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
        file.setStatus(ProjectFileStatus.ACTIVE);

        when(projectMapper.selectById(10L)).thenReturn(project);
        when(fileMapper.selectById(30L)).thenReturn(file);
        service = new FileDetailAnalysisService(
                projectMapper,
                fileMapper,
                new FileStorageLocationFactory(),
                objectStorageService,
                projectIndexService,
                new MinioProperties(),
                new ObjectMapper().registerModule(new JavaTimeModule()),
                ingestBatchService
        );
    }

    @Test
    void successShouldWriteFullDetailAndRefreshIndex() {
        when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(1);
        FileAnalysisResultRequest request = successRequest();

        service.saveResult(10L, 30L, "event-1", request);

        verify(objectStorageService).putObject(
                org.mockito.ArgumentMatchers.eq(new StorageLocation(
                        "pm-agent",
                        "PM-AGENT/1/10/system/file_details/README-a1b2c3d4e5f67890.md"
                )),
                any(byte[].class),
                org.mockito.ArgumentMatchers.eq("application/json")
        );
        verify(projectIndexService).rebuild(project);
    }

    @Test
    void staleHashShouldBeRejectedBeforeWritingDetail() {
        FileAnalysisResultRequest request = new FileAnalysisResultRequest(
                "event-1",
                null,
                "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "file-detail-v1",
                FileAnalysisResultStatus.SUCCESS,
                successRequest().detail(),
                null,
                null
        );

        assertThatThrownBy(() -> service.saveResult(10L, 30L, "event-1", request))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("哈希");
        verify(objectStorageService, never()).putObject(any(), any(), any());
        verify(projectIndexService, never()).rebuild(any(Project.class));
    }

    @Test
    void failureShouldOnlyPersistFailureProjection() {
        when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(1);
        FileAnalysisResultRequest request = new FileAnalysisResultRequest(
                "event-1",
                null,
                "sha256:" + file.getContentHash(),
                "file-detail-v1",
                FileAnalysisResultStatus.FAILED,
                null,
                "FILE_DETAIL_PARSE_FAILED",
                "解析器异常"
        );

        service.saveResult(10L, 30L, "event-1", request);

        verify(objectStorageService, never()).putObject(any(), any(), any());
        verify(projectIndexService).rebuild(project);
    }

    private FileAnalysisResultRequest successRequest() {
        LocalDateTime now = LocalDateTime.of(2026, 7, 16, 10, 10);
        FileDetailDocument detail = new FileDetailDocument(
                "file-30",
                10L,
                30L,
                "1.0.0",
                "file-detail-v1",
                now,
                now,
                file.getStorageUuid(),
                file.getStorageName(),
                file.getDetailRef(),
                file.getRelativePath(),
                file.getMinioPath(),
                100L,
                "text/markdown",
                "sha256:" + file.getContentHash(),
                "backend",
                "documentation",
                "doc",
                "markdown",
                "active",
                "medium",
                "后端模块说明文档",
                List.of("Spring Boot", "MinIO"),
                "说明后端模块的启动和存储约定",
                List.of(new FileDetailDocument.ContentSlice(
                        "overview",
                        "doc",
                        "说明后端模块",
                        List.of("backend", "MinIO", "Spring Boot"),
                        List.of("system/file_details"),
                        new FileDetailDocument.SourceRange(1, 10)
                )),
                List.of("文件存储"),
                List.of(),
                List.of(),
                List.of(),
                List.of(new FileDetailDocument.Evidence("file_content", "后端说明")),
                List.of(),
                new FileDetailDocument.ParserMetadata(
                        "deterministic_structure",
                        "deterministic-file-detail-v1",
                        false,
                        10
                )
        );
        return new FileAnalysisResultRequest(
                "event-1",
                null,
                "sha256:" + file.getContentHash(),
                "file-detail-v1",
                FileAnalysisResultStatus.SUCCESS,
                detail,
                null,
                null
        );
    }
}
