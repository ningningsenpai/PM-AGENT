package com.ning.pm.project.context;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.converter.ProjectFileIndexConverterImpl;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.domain.Project;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * ProjectIndexFactoryTest 验证项目上下文索引结构、对象路径和失败清单。
 *
 * @author ning
 * @date 2026-07-15
 */
class ProjectIndexFactoryTest {

    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
    private final FileStorageLocationFactory locationFactory = new FileStorageLocationFactory();
    private final ProjectIndexFactory factory = new ProjectIndexFactory(
            new ProjectIndexTemplateLoader(objectMapper),
            locationFactory,
            new ProjectFileIndexConverterImpl()
    );

    @Test
    void initialIndexShouldMatchFixedStructure() throws Exception {
        ProjectIndex index = factory.createInitialIndex(project());

        String json = objectMapper.writeValueAsString(index);

        assertThat(index.schemaVersion()).isEqualTo("1.0.0");
        assertThat(index.storage().bucket()).isEqualTo("pm-agent");
        assertThat(index.storage().objectPrefix()).isEqualTo("PM-AGENT/1/10/");
        assertThat(index.system().index()).isEqualTo("system/index.json");
        assertThat(index.system().longTermMemory()).isEqualTo("system/long_term_memory.json");
        assertThat(json).contains("\"project\":[]", "\"user\":[]", "\"system\":");
        assertThat(json).contains("\"fail_nodes\":0");
        assertThat(json).doesNotContain(
                "entries",
                "ignored_nodes",
                "failed_files",
                "pending_analysis_files",
                "detail_files",
                "analysis_status",
                "detail_ref",
                "file_details"
        );
    }

    @Test
    void currentIndexShouldSeparateActiveAndFailedFiles() {
        ProjectFile active = file(30L, ProjectFileStatus.ACTIVE, "README.md", "a1b2c3d4e5f67890");
        active.setDetailRef("system/file_details/README-a1b2c3d4e5f67890.json");
        active.setAnalysisVersion("file-detail-v1");
        active.setModule("docs");
        active.setKind("documentation");
        active.setFileType("doc");
        active.setLanguage("markdown");
        active.setImportance("medium");
        active.setSummary("项目说明");
        active.setKeywords(List.of("项目文件"));
        ProjectFile failed = file(31L, ProjectFileStatus.UPLOAD_FAILED, "Broken.java", "b1c2d3e4f5a67890");
        failed.setUploadAttempts(3);
        failed.setLastErrorCode("FILE_STORAGE_ERROR");

        ProjectIndex index = factory.buildCurrentIndex(
                project(),
                ProjectScanSummary.fromStoredFiles(2),
                List.of(active, failed)
        );

        assertThat(index.project()).hasSize(1);
        assertThat(index.project().get(0).storageName())
                .isEqualTo("README-a1b2c3d4e5f67890.md");
        assertThat(index.project().get(0).minioPath())
                .isEqualTo("project/README-a1b2c3d4e5f67890.md");
        assertThat(index.project().get(0).detailRef())
                .isEqualTo("system/file_details/README-a1b2c3d4e5f67890.json");
        assertThat(index.project().get(0).module()).isEqualTo("docs");
        assertThat(index.project().get(0).keywords()).containsExactly("项目文件");
        assertThat(index.uploadFailures()).hasSize(1);
        assertThat(index.uploadFailures().get(0).attempts()).isEqualTo(3);
        assertThat(index.summary().activeFiles()).isEqualTo(1);
        assertThat(index.summary().failNodes()).isEqualTo(1);
    }

    private Project project() {
        Project project = new Project();
        project.setId(10L);
        project.setOwnerUserId(1L);
        project.setProjectName("PM-Agent");
        return project;
    }

    private ProjectFile file(
            Long id,
            ProjectFileStatus status,
            String fileName,
            String storageUuid
    ) {
        ProjectFile file = new ProjectFile();
        file.setId(id);
        file.setProjectId(10L);
        file.setBusinessCode(FileBusinessType.PROJECT);
        file.setRelativePath("backend/" + fileName);
        file.setFileName(fileName);
        file.setExtension(fileName.substring(fileName.lastIndexOf('.') + 1));
        file.setStorageUuid(storageUuid);
        file.setObjectKey(locationFactory.buildProjectFile(
                1L,
                10L,
                fileName,
                storageUuid
        ).objectKey());
        file.setSizeBytes(100L);
        file.setContentType("text/plain");
        file.setStatus(status);
        file.setQuickFingerprint("quick");
        file.setContentHash("content");
        file.setUpdatedAt(LocalDateTime.of(2026, 7, 15, 10, 0));
        return file;
    }
}
