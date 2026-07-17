package com.ning.pm.project.context;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.context.dto.ProjectIndexTemplate;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.SystemFilePath;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;

/**
 * ProjectIndexFactory 只依据项目、扫描统计和数据库文件记录构建完整索引。
 *
 * @author ning
 * @date 2026-07-15
 */
@Component
@RequiredArgsConstructor
public class ProjectIndexFactory {

    private final ProjectIndexTemplateLoader templateLoader;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectMapper objectMapper;

    public ProjectIndex createInitialIndex(Project project) {
        ProjectIndexTemplate template = templateLoader.load();
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime generatedAt = project.getCreatedAt() == null ? now : project.getCreatedAt();
        return new ProjectIndex(
                project.getId(),
                project.getProjectName(),
                project.getOwnerUserId(),
                template.schemaVersion(),
                generatedAt,
                now,
                createStorage(project),
                new ProjectIndex.Summary(0, 0, 0),
                List.of(),
                List.of(),
                List.of(),
                createSystemSection()
        );
    }

    public ProjectIndex buildCurrentIndex(
            Project project,
            ProjectScanSummary scanSummary,
            List<ProjectFile> files
    ) {
        ProjectIndexTemplate template = templateLoader.load();
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime generatedAt = project.getCreatedAt() == null ? now : project.getCreatedAt();
        List<ProjectIndex.FileEntry> projectFiles = activeEntries(
                project,
                files,
                FileBusinessType.PROJECT
        );
        List<ProjectIndex.FileEntry> userFiles = activeEntries(
                project,
                files,
                FileBusinessType.USER
        );
        List<ProjectIndex.UploadFailure> failures = files.stream()
                .filter(file -> file.getStatus() == ProjectFileStatus.UPLOAD_FAILED
                        || file.getStatus() == ProjectFileStatus.VERIFY_REQUIRED)
                .map(file -> toFailure(project, file, now))
                .toList();
        long activeFiles = projectFiles.size() + userFiles.size();
        long analysisFailures = files.stream()
                .filter(file -> file.getStatus() == ProjectFileStatus.ACTIVE)
                .filter(file -> file.getAnalysisStatus() != null
                        && "failed".equals(file.getAnalysisStatus().getCode()))
                .count();
        return new ProjectIndex(
                project.getId(),
                project.getProjectName(),
                project.getOwnerUserId(),
                template.schemaVersion(),
                generatedAt,
                now,
                createStorage(project),
                new ProjectIndex.Summary(
                        scanSummary.totalNodes(),
                        activeFiles,
                        scanSummary.scanErrorNodes() + failures.size() + analysisFailures
                ),
                projectFiles,
                userFiles,
                failures,
                createSystemSection()
        );
    }

    private List<ProjectIndex.FileEntry> activeEntries(
            Project project,
            List<ProjectFile> files,
            FileBusinessType businessType
    ) {
        return files.stream()
                .filter(file -> file.getBusinessCode() == businessType)
                .filter(file -> file.getStatus() == ProjectFileStatus.ACTIVE)
                .map(file -> toFileEntry(project, file))
                .toList();
    }

    private ProjectIndex.FileEntry toFileEntry(Project project, ProjectFile file) {
        String storageName = valueOrFallback(
                file.getStorageName(),
                locationFactory.buildStorageName(file.getFileName(), file.getStorageUuid())
        );
        String minioPath = valueOrFallback(
                file.getMinioPath(),
                locationFactory.relativeObjectPath(
                        project.getOwnerUserId(),
                        project.getId(),
                        file.getObjectKey()
                )
        );
        return new ProjectIndex.FileEntry(
                file.getId(),
                file.getStorageUuid(),
                file.getRelativePath(),
                file.getFileName(),
                storageName,
                minioPath,
                file.getSizeBytes(),
                file.getContentType(),
                file.getStatus().getCode(),
                file.getAnalysisStatus() == null ? "pending" : file.getAnalysisStatus().getCode(),
                prefixHash("qf:sha256:", file.getQuickFingerprint()),
                prefixHash("sha256:", file.getContentHash()),
                file.getAnalysisModule(),
                file.getAnalysisKind(),
                valueOrFallback(file.getAnalysisLanguage(), detectLanguage(file.getExtension())),
                file.getAnalysisImportance(),
                file.getAnalysisSummary(),
                parseKeywords(file.getAnalysisKeywords()),
                valueOrFallback(
                        file.getDetailRef(),
                        systemPath(SystemFilePath.FILE_DETAILS.directoryPath()) + storageName
                ),
                file.getUpdatedAt()
        );
    }

    private ProjectIndex.UploadFailure toFailure(
            Project project,
            ProjectFile file,
            LocalDateTime fallbackUpdatedAt
    ) {
        return new ProjectIndex.UploadFailure(
                file.getId(),
                file.getBusinessCode().getCode(),
                file.getRelativePath(),
                file.getFileName(),
                locationFactory.buildStorageName(file.getFileName(), file.getStorageUuid()),
                file.getStatus().getCode(),
                file.getUploadAttempts(),
                file.getLastErrorCode(),
                file.getUpdatedAt() == null ? fallbackUpdatedAt : file.getUpdatedAt()
        );
    }

    private ProjectIndex.Storage createStorage(Project project) {
        StorageLocation prefix = locationFactory.buildProjectPrefix(
                project.getOwnerUserId(),
                project.getId()
        );
        return new ProjectIndex.Storage(
                "minio",
                prefix.bucket(),
                prefix.objectKey(),
                "system/index.json"
        );
    }

    private ProjectIndex.SystemSection createSystemSection() {
        return new ProjectIndex.SystemSection(
                systemPath(SystemFilePath.INDEX.fixedPath()),
                systemPath(SystemFilePath.FILE_DETAILS.directoryPath()),
                systemPath(SystemFilePath.PROJECT_SPECIFICATION.fixedPath()),
                systemPath(SystemFilePath.LONG_TERM_MEMORY.fixedPath()),
                systemPath(SystemFilePath.SHORT_TERM_MEMORY.fixedPath()),
                systemPath(SystemFilePath.USER_HABITS.directoryPath()),
                systemPath(SystemFilePath.UPDATE_JOURNAL.fixedPath())
        );
    }

    private String systemPath(String path) {
        return "system/" + path;
    }

    private String prefixHash(String prefix, String hash) {
        return hash == null || hash.isBlank() ? null : prefix + hash;
    }

    private List<String> parseKeywords(String keywordsJson) {
        if (keywordsJson == null || keywordsJson.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(keywordsJson, new TypeReference<List<String>>() {
            });
        } catch (Exception ignored) {
            return List.of();
        }
    }

    private String valueOrFallback(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private String detectLanguage(String extension) {
        if (extension == null || extension.isBlank()) {
            return null;
        }
        return switch (extension.toLowerCase(Locale.ROOT)) {
            case "md", "markdown" -> "markdown";
            case "js", "jsx" -> "javascript";
            case "ts", "tsx" -> "typescript";
            case "py" -> "python";
            case "java" -> "java";
            case "kt", "kts" -> "kotlin";
            case "yml", "yaml" -> "yaml";
            default -> extension.toLowerCase(Locale.ROOT);
        };
    }
}
