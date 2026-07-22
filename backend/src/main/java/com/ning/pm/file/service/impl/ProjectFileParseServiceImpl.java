package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.file.domain.AgentServiceApi;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import com.ning.pm.file.dto.parse.FileAnalysisResult;
import com.ning.pm.file.dto.parse.FileDetail;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.file.service.ParseFileDataFactory;
import com.ning.pm.file.service.ProjectFileParseService;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexWriter;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.net.URI;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * ProjectFileParseServiceImpl 负责校验项目归属并调用 Agent 文件解析接口。
 *
 * @author ning
 * @date 2026-07-22
 */
@Service
@RequiredArgsConstructor
public class ProjectFileParseServiceImpl implements ProjectFileParseService {

    private static final String ANALYSIS_SUCCESS = "success";
    private static final String ANALYSIS_FAILED = "failed";
    private static final String DETAIL_REF_PREFIX = "system/file_details/";
    private static final RestClient REST_CLIENT = RestClient.create();

    private final ProjectService projectService;
    private final ParseFileDataFactory parseFileDataFactory;
    private final ProjectFileMapper projectFileMapper;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectStorageService objectStorageService;
    private final ProjectIndexWriter projectIndexWriter;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate transactionTemplate;

    @Override
    public void initParseFiles(Long projectId) {
        Project project = projectService.requireOwnedProject(projectId);
        List<FileAnalysisRequest> requests = parseFileDataFactory.getInitParseData(projectId);
        if (requests.isEmpty()) {
            completeProjectIndex(project);
            return;
        }

        List<FileAnalysisResult> results = requestFileAnalysis(requests);
        validateAnalysisResults(projectId, requests, results);
        uploadFileDetails(project, results);
        persistAnalysisResults(projectId, results);
        completeProjectIndex(project);
    }

    private List<FileAnalysisResult> requestFileAnalysis(List<FileAnalysisRequest> requests) {
        List<FileAnalysisResult> results = REST_CLIENT.post()
                .uri(AgentServiceApi.PROJECT_FILE_ANALYZE.getUrl())
                .header("X-Trace-Id", TraceContext.getTraceId())
                .body(requests)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (results == null) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析接口未返回结果");
        }
        return results;
    }

    private void validateAnalysisResults(
            Long projectId,
            List<FileAnalysisRequest> requests,
            List<FileAnalysisResult> results
    ) {
        if (results.size() != requests.size()) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果数量与请求数量不一致");
        }
        Map<Long, FileAnalysisRequest> requestByFileId = new HashMap<>();
        for (FileAnalysisRequest request : requests) {
            requestByFileId.put(request.fileId(), request);
        }
        Set<Long> resultFileIds = new HashSet<>();
        for (FileAnalysisResult result : results) {
            if (result == null || result.fileId() == null || !resultFileIds.add(result.fileId())) {
                throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果包含空值或重复文件");
            }
            FileAnalysisRequest request = requestByFileId.get(result.fileId());
            if (request == null
                    || !projectId.equals(result.projectId())
                    || !sameText(request.contentHash(), result.contentHash())
                    || !sameText(request.analysisVersion(), result.analysisVersion())) {
                throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果与原始请求不一致");
            }
            if (ANALYSIS_SUCCESS.equals(result.status())) {
                validateSuccessfulResult(request, result.detail());
            } else if (!ANALYSIS_FAILED.equals(result.status()) || result.detail() != null) {
                throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果状态不合法");
            }
        }
    }

    private void validateSuccessfulResult(FileAnalysisRequest request, FileDetail detail) {
        if (detail == null
                || !request.projectId().equals(detail.projectId())
                || !request.fileId().equals(detail.fileId())
                || !sameText(request.storageUuid(), detail.storageUuid())
                || !sameText(request.storageName(), detail.storageName())
                || !sameText(request.detailRef(), detail.detailRef())
                || !sameText(request.originalPath(), detail.originalPath())
                || !sameText(request.minioPath(), detail.minioPath())
                || !request.sizeBytes().equals(detail.sizeBytes())
                || !sameText(request.contentType(), detail.contentType())
                || !sameText(request.contentHash(), detail.contentHash())
                || !sameText(request.analysisVersion(), detail.analysisVersion())) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 返回的文件详情身份字段不一致");
        }
        validateDetailRef(detail.detailRef());
    }

    private void uploadFileDetails(Project project, List<FileAnalysisResult> results) {
        for (FileAnalysisResult result : results) {
            if (!ANALYSIS_SUCCESS.equals(result.status())) {
                continue;
            }
            FileDetail detail = result.detail();
            try {
                byte[] content = objectMapper.writerWithDefaultPrettyPrinter()
                        .writeValueAsBytes(detail);
                objectStorageService.putObject(
                        detailLocation(project, detail.detailRef()),
                        content,
                        "application/json"
                );
            } catch (IOException exception) {
                throw new SystemException(
                        ErrorCode.FILE_STORAGE_ERROR,
                        "文件详情序列化失败",
                        exception
                );
            }
        }
    }

    private StorageLocation detailLocation(Project project, String detailRef) {
        validateDetailRef(detailRef);
        StorageLocation prefix = locationFactory.buildProjectPrefix(
                project.getOwnerUserId(),
                project.getId()
        );
        return new StorageLocation(prefix.bucket(), prefix.objectKey() + detailRef);
    }

    private void validateDetailRef(String detailRef) {
        if (detailRef == null
                || !detailRef.startsWith(DETAIL_REF_PREFIX)
                || !detailRef.endsWith(".json")
                || detailRef.length() <= DETAIL_REF_PREFIX.length() + ".json".length()
                || detailRef.contains("\\")
                || detailRef.contains("..")
                || detailRef.contains("//")) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件详情引用路径不合法");
        }
    }

    private void persistAnalysisResults(Long projectId, List<FileAnalysisResult> results) {
        transactionTemplate.executeWithoutResult(transactionStatus -> {
            for (FileAnalysisResult result : results) {
                ProjectFile update = new ProjectFile();
                if (ANALYSIS_SUCCESS.equals(result.status())) {
                    FileDetail detail = result.detail();
                    update.setDetailRef(detail.detailRef());
                    update.setAnalysisVersion(detail.analysisVersion());
                    update.setModule(detail.module());
                    update.setKind(detail.kind());
                    update.setFileType(detail.fileType());
                    update.setLanguage(detail.language());
                    update.setImportance(detail.importance());
                    update.setSummary(detail.summary());
                    update.setKeywords(detail.keywords());
                }

                int affectedRows = projectFileMapper.update(
                        update,
                        new LambdaUpdateWrapper<ProjectFile>()
                                .eq(ProjectFile::getId, result.fileId())
                                .eq(ProjectFile::getProjectId, projectId)
                                .eq(ProjectFile::getContentHash, result.contentHash())
                                .setSql("parse_attempts = parse_attempts + 1")
                );
                if (affectedRows != 1) {
                    throw new SystemException(
                            ErrorCode.SYSTEM_ERROR,
                            "文件分析结果落库失败，文件可能已发生变化"
                    );
                }
            }
        });
    }

    /**
     * 下载现有 index.json，根据最新数据库记录补全文件条目后整体覆盖上传。
     */
    private void completeProjectIndex(Project project) {
        StorageLocation indexLocation = projectIndexWriter.indexLocation(
                project.getOwnerUserId(),
                project.getId()
        );
        ObjectNode index = downloadProjectIndex(indexLocation);
        List<ProjectFile> files = projectFileMapper.selectList(
                new LambdaQueryWrapper<ProjectFile>()
                        .eq(ProjectFile::getProjectId, project.getId())
                        .orderByAsc(ProjectFile::getBusinessCode)
                        .orderByAsc(ProjectFile::getRelativePath)
        );

        ArrayNode projectFiles = objectMapper.createArrayNode();
        ArrayNode userFiles = objectMapper.createArrayNode();
        long failNodes = 0L;
        for (ProjectFile file : files) {
            if (file.getUploadStatus() == ProjectFileUploadStatus.NOT_UPLOADED
                    || file.getStatus() == ProjectFileStatus.UPLOAD_FAILED
                    || file.getStatus() == ProjectFileStatus.VERIFY_REQUIRED) {
                failNodes++;
            }
            if (file.getStatus() != ProjectFileStatus.ACTIVE
                    || (file.getUploadStatus() != null
                    && file.getUploadStatus() != ProjectFileUploadStatus.SUCCESS)) {
                continue;
            }
            if (file.getBusinessCode() == FileBusinessType.PROJECT) {
                projectFiles.add(toIndexEntry(file));
            } else if (file.getBusinessCode() == FileBusinessType.USER) {
                userFiles.add(toIndexEntry(file));
            }
        }

        index.set("project", projectFiles);
        index.set("user", userFiles);
        index.put("updated_at", LocalDateTime.now().toString());
        ObjectNode summary = index.get("summary") instanceof ObjectNode currentSummary
                ? currentSummary
                : objectMapper.createObjectNode();
        summary.put("total_nodes", files.size());
        summary.put("active_files", projectFiles.size() + userFiles.size());
        summary.put("fail_nodes", failNodes);
        index.set("summary", summary);

        try {
            byte[] content = objectMapper.writerWithDefaultPrettyPrinter()
                    .writeValueAsBytes(index);
            objectStorageService.putObject(indexLocation, content, "application/json");
        } catch (IOException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                    "项目上下文索引序列化失败",
                    exception
            );
        }
    }

    private ObjectNode downloadProjectIndex(StorageLocation indexLocation) {
        String readUrl = objectStorageService.createReadUrl(indexLocation);
        byte[] content = REST_CLIENT.get()
                .uri(URI.create(readUrl))
                .retrieve()
                .body(byte[].class);
        if (content == null || content.length == 0) {
            throw new SystemException(ErrorCode.PROJECT_INDEX_WRITE_FAILED, "项目上下文索引内容为空");
        }
        try {
            JsonNode index = objectMapper.readTree(content);
            if (index instanceof ObjectNode objectNode) {
                return objectNode;
            }
            throw new SystemException(ErrorCode.PROJECT_INDEX_WRITE_FAILED, "项目上下文索引格式不正确");
        } catch (IOException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                    "项目上下文索引解析失败",
                    exception
            );
        }
    }

    private ObjectNode toIndexEntry(ProjectFile file) {
        ObjectNode entry = objectMapper.createObjectNode();
        entry.set("id", objectMapper.valueToTree(file.getId()));
        entry.set("storage_uuid", objectMapper.valueToTree(file.getStorageUuid()));
        entry.set("logical_path", objectMapper.valueToTree(file.getRelativePath()));
        entry.set("file_name", objectMapper.valueToTree(file.getFileName()));
        entry.set("storage_name", objectMapper.valueToTree(file.getStorageName()));
        entry.set("minio_path", objectMapper.valueToTree(file.getMinioPath()));
        entry.set("size_bytes", objectMapper.valueToTree(file.getSizeBytes()));
        entry.set("content_type", objectMapper.valueToTree(file.getContentType()));
        entry.set("status", objectMapper.valueToTree(file.getStatus().getCode()));
        entry.set("quick_fingerprint", objectMapper.valueToTree(
                prefixHash("qf:sha256:", file.getQuickFingerprint())
        ));
        entry.set("content_hash", objectMapper.valueToTree(
                prefixHash("sha256:", file.getContentHash())
        ));
        entry.set("updated_at", objectMapper.valueToTree(file.getUpdatedAt()));
        entry.set("detail_ref", objectMapper.valueToTree(file.getDetailRef()));
        entry.set("analysis_version", objectMapper.valueToTree(file.getAnalysisVersion()));
        entry.set("module", objectMapper.valueToTree(file.getModule()));
        entry.set("kind", objectMapper.valueToTree(file.getKind()));
        entry.set("file_type", objectMapper.valueToTree(file.getFileType()));
        entry.set("language", objectMapper.valueToTree(file.getLanguage()));
        entry.set("importance", objectMapper.valueToTree(file.getImportance()));
        entry.set("summary", objectMapper.valueToTree(file.getSummary()));
        entry.set("keywords", objectMapper.valueToTree(
                file.getKeywords() == null ? List.of() : file.getKeywords()
        ));
        return entry;
    }

    private String prefixHash(String prefix, String hash) {
        return hash == null || hash.isBlank() ? null : prefix + hash;
    }

    private boolean sameText(String left, String right) {
        return left == null ? right == null : left.equals(right);
    }

}
