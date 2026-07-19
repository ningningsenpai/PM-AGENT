package com.ning.pm.file.analysis;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.analysis.dto.FileAnalysisResultRequest;
import com.ning.pm.file.analysis.dto.FileAnalysisResultStatus;
import com.ning.pm.file.analysis.dto.FileDetailDocument;
import com.ning.pm.file.analysis.dto.InternalFileReadUrlResponse;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.ProjectFileAnalysisStatus;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.MinioProperties;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.domain.SystemFilePath;
import com.ning.pm.project.repository.ProjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Set;

/**
 * 接收 Python 详情解析结果，由 Java 统一写 MinIO、落 MySQL 投影字段并刷新索引。
 */
@Service
@RequiredArgsConstructor
public class FileDetailAnalysisService {

    private static final Set<String> IMPORTANCE_VALUES = Set.of("high", "medium", "low");

    private final ProjectMapper projectMapper;
    private final ProjectFileMapper fileMapper;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectStorageService objectStorageService;
    private final ProjectIndexService projectIndexService;
    private final MinioProperties minioProperties;
    private final ObjectMapper objectMapper;

    public InternalFileReadUrlResponse createReadUrl(Long projectId, Long fileId) {
        Project project = requireActiveProject(projectId);
        ProjectFile file = requireActiveFile(projectId, fileId);
        String sourceUrl = objectStorageService.createReadUrl(new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                file.getObjectKey()
        ));
        return new InternalFileReadUrlResponse(
                sourceUrl,
                LocalDateTime.now().plusSeconds(minioProperties.getReadUrlExpirySeconds())
        );
    }

    public void saveResult(
            Long projectId,
            Long fileId,
            String idempotencyKey,
            FileAnalysisResultRequest request
    ) {
        if (!request.eventId().equals(idempotencyKey)) {
            throw invalidResult("幂等键必须与事件 ID 一致");
        }
        Project project = requireActiveProject(projectId);
        ProjectFile file = requireActiveFile(projectId, fileId);
        requireCurrentContent(file, request.contentHash());
        if (!java.util.Objects.equals(file.getIngestBatchId(), request.batchId())) {
            throw invalidResult("回调批次 ID 与当前文件不一致");
        }

        if (request.status() == FileAnalysisResultStatus.FAILED) {
            saveFailure(project, file, request);
            return;
        }
        if (request.detail() == null) {
            throw invalidResult("成功结果必须包含完整详情文档");
        }

        FileDetailDocument detail = request.detail();
        validateDetail(project, file, request, detail);
        byte[] detailBytes = serializeDetail(detail);
        objectStorageService.putObject(
                locationFactory.buildSystemFile(
                        project.getOwnerUserId(),
                        project.getId(),
                        SystemFilePath.FILE_DETAILS,
                        file.getStorageName()
                ),
                detailBytes,
                "application/json"
        );

        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getProjectId, project.getId())
                .eq(ProjectFile::getContentHash, file.getContentHash())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.SUCCESS)
                .set(ProjectFile::getAnalysisVersion, detail.analysisVersion())
                .set(ProjectFile::getDetailRef, detail.detailRef())
                .set(ProjectFile::getAnalysisModule, detail.module())
                .set(ProjectFile::getAnalysisKind, detail.kind())
                .set(ProjectFile::getAnalysisLanguage, detail.language())
                .set(ProjectFile::getAnalysisImportance, detail.importance())
                .set(ProjectFile::getAnalysisSummary, detail.summary())
                .set(ProjectFile::getAnalysisKeywords, serializeKeywords(detail))
                .set(ProjectFile::getAnalysisErrorCode, null)
                .set(ProjectFile::getAnalysisErrorMessage, null)
                .set(ProjectFile::getAnalyzedAt, LocalDateTime.now())
                .setSql("analysis_attempts = analysis_attempts + 1"));
        if (updated == 0) {
            throw invalidResult("文件内容已变化，旧解析结果不能覆盖当前版本");
        }
        finishAnalysis(project);
    }

    private void saveFailure(Project project, ProjectFile file, FileAnalysisResultRequest request) {
        if (request.detail() != null) {
            throw invalidResult("失败结果不能携带详情文档");
        }
        int updated = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getProjectId, project.getId())
                .eq(ProjectFile::getContentHash, file.getContentHash())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.FAILED)
                .set(ProjectFile::getAnalysisVersion, request.analysisVersion())
                .set(ProjectFile::getAnalysisErrorCode, normalizeError(request.errorCode(), "FILE_ANALYSIS_FAILED"))
                .set(ProjectFile::getAnalysisErrorMessage, normalizeError(request.errorMessage(), "文件详情解析失败"))
                .setSql("analysis_attempts = analysis_attempts + 1"));
        if (updated == 0) {
            throw invalidResult("文件内容已变化，失败结果不再适用于当前版本");
        }
        finishAnalysis(project);
    }

    private void finishAnalysis(Project project) {
        projectIndexService.rebuild(project);
    }

    private void validateDetail(
            Project project,
            ProjectFile file,
            FileAnalysisResultRequest request,
            FileDetailDocument detail
    ) {
        String expectedDetailRef = "system/" + SystemFilePath.FILE_DETAILS.directoryPath() + file.getStorageName();
        boolean identityMismatch = !project.getId().equals(detail.projectId())
                || !file.getId().equals(detail.fileId())
                || !file.getStorageUuid().equals(detail.storageUuid())
                || !file.getStorageName().equals(detail.storageName())
                || !file.getRelativePath().equals(detail.originalPath())
                || !file.getMinioPath().equals(detail.minioPath())
                || !expectedDetailRef.equals(detail.detailRef())
                || !request.analysisVersion().equals(detail.analysisVersion())
                || !sameHash(file.getContentHash(), detail.contentHash());
        if (identityMismatch) {
            throw invalidResult("详情文档身份字段与数据库文件记录不一致");
        }
        if (!IMPORTANCE_VALUES.contains(detail.importance())) {
            throw invalidResult("importance 只能是 high、medium 或 low");
        }
        if (!"active".equals(detail.status())) {
            throw invalidResult("当前活动文件的详情状态必须是 active");
        }
        detail.contentSlices().stream()
                .filter(slice -> slice.sourceRange() != null)
                .filter(slice -> slice.sourceRange().endLine() < slice.sourceRange().startLine())
                .findFirst()
                .ifPresent(slice -> {
                    throw invalidResult("内容切片结束行不能小于开始行");
                });
    }

    private Project requireActiveProject(Long projectId) {
        Project project = projectMapper.selectById(projectId);
        if (project == null) {
            throw new BizException(ErrorCode.PROJECT_NOT_FOUND);
        }
        if (project.getStatus() != ProjectStatus.ACTIVE) {
            throw new BizException(ErrorCode.PROJECT_DISABLED);
        }
        return project;
    }

    private ProjectFile requireActiveFile(Long projectId, Long fileId) {
        ProjectFile file = fileMapper.selectById(fileId);
        if (file == null || !projectId.equals(file.getProjectId())) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND);
        }
        if (file.getStatus() != ProjectFileStatus.ACTIVE) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID);
        }
        return file;
    }

    private void requireCurrentContent(ProjectFile file, String callbackHash) {
        if (!sameHash(file.getContentHash(), callbackHash)) {
            throw invalidResult("回调内容哈希与当前文件不一致");
        }
    }

    private boolean sameHash(String databaseHash, String externalHash) {
        return databaseHash != null && databaseHash.equals(stripSha256Prefix(externalHash));
    }

    private String stripSha256Prefix(String value) {
        if (value == null) {
            return null;
        }
        return value.startsWith("sha256:") ? value.substring("sha256:".length()) : value;
    }

    private byte[] serializeDetail(FileDetailDocument detail) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(detail);
        } catch (JsonProcessingException exception) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "详情文档序列化失败", exception);
        }
    }

    private String serializeKeywords(FileDetailDocument detail) {
        try {
            return objectMapper.writeValueAsString(detail.keywords());
        } catch (JsonProcessingException exception) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "索引关键词序列化失败", exception);
        }
    }

    private String normalizeError(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private BizException invalidResult(String message) {
        return new BizException(ErrorCode.FILE_ANALYSIS_RESULT_INVALID, message);
    }
}
