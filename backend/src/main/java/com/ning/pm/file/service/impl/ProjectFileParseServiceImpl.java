package com.ning.pm.file.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.file.converter.ParseFileDataConverter;
import com.ning.pm.file.converter.ProjectFileIndexConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import com.ning.pm.file.dto.parse.FileAnalysisResult;
import com.ning.pm.file.dto.parse.FileDetail;
import com.ning.pm.file.enums.AgentServiceApi;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.ParseFileDataFactory;
import com.ning.pm.file.service.ProjectFileParseService;
import com.ning.pm.file.service.storage.FileDetailStorageLocationResolver;
import com.ning.pm.file.service.validation.FileAnalysisResultValidator;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.ProjectIndexWriter;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.context.json.FileDetailJsonSerializer;
import com.ning.pm.project.context.json.ProjectIndexJsonCodec;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.client.RestClient;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;

/**
 * ProjectFileParseServiceImpl 负责校验项目归属并编排文件解析、落库和索引补全流程。
 *
 * @author ning
 * @date 2026-07-22
 */
@Service
@RequiredArgsConstructor
public class ProjectFileParseServiceImpl implements ProjectFileParseService {

    private static final RestClient REST_CLIENT = RestClient.create();

    private final ProjectService projectService;
    private final ParseFileDataFactory parseFileDataFactory;
    private final ProjectFileMapper projectFileMapper;
    private final ObjectStorageService objectStorageService;
    private final ProjectIndexWriter projectIndexWriter;
    private final TransactionTemplate transactionTemplate;
    private final FileAnalysisResultValidator analysisResultValidator;
    private final FileDetailStorageLocationResolver detailLocationResolver;
    private final FileDetailJsonSerializer fileDetailJsonSerializer;
    private final ProjectIndexJsonCodec projectIndexJsonCodec;
    private final ParseFileDataConverter parseFileDataConverter;
    private final ProjectFileIndexConverter projectFileIndexConverter;

    @Override
    public void initParseFiles(Long projectId) {
        Project project = projectService.requireOwnedProject(projectId);
        List<FileAnalysisRequest> requests = parseFileDataFactory.getInitParseData(projectId);
        if (requests.isEmpty()) {
            completeProjectIndex(project);
            return;
        }

        List<FileAnalysisResult> results = requestFileAnalysis(requests);
        analysisResultValidator.validate(projectId, requests, results);
        uploadFileDetails(project, results);
        persistAnalysisResults(projectId, results);
        completeProjectIndex(project);
    }

    /** 调用 Agent 文件分析接口，返回分析结果。 */
    private List<FileAnalysisResult> requestFileAnalysis(List<FileAnalysisRequest> requests) {
        return REST_CLIENT.post()
                .uri(AgentServiceApi.PROJECT_FILE_ANALYZE.getUrl())
                .header("X-Trace-Id", TraceContext.getTraceId())
                .body(requests)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
    }

    /** 将解析成功的文件详情上传到 detailRef 对应的 MinIO 位置。 */
    private void uploadFileDetails(Project project, List<FileAnalysisResult> results) {
        for (FileAnalysisResult result : results) {
            if (!analysisResultValidator.isSuccessful(result)) {
                continue;
            }
            FileDetail detail = result.detail();
            objectStorageService.putObject(
                    detailLocationResolver.resolve(project, detail.detailRef()),
                    fileDetailJsonSerializer.serialize(detail),
                    "application/json"
            );
        }
    }

    /** 持久化文件分析结果到数据库。 */
    private void persistAnalysisResults(Long projectId, List<FileAnalysisResult> results) {
        transactionTemplate.executeWithoutResult(transactionStatus -> {
            for (FileAnalysisResult result : results) {
                ProjectFile update = analysisResultValidator.isSuccessful(result)
                        ? parseFileDataConverter.toProjectFileUpdate(result.detail())
                        : new ProjectFile();

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

    /** 下载现有 index.json，根据最新数据库记录补全文件条目后整体覆盖上传。 */
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

        List<ProjectIndex.FileEntry> projectFiles = new ArrayList<>();
        List<ProjectIndex.FileEntry> userFiles = new ArrayList<>();
        long failNodes = 0L;
        for (ProjectFile file : files) {
            if (isFailedFile(file)) {
                failNodes++;
            }
            if (!isActiveFile(file)) {
                continue;
            }

            ProjectIndex.FileEntry entry = projectFileIndexConverter.toIndexEntry(
                    file,
                    file.getStorageName(),
                    file.getMinioPath()
            );
            if (file.getBusinessCode() == FileBusinessType.PROJECT) {
                projectFiles.add(entry);
            } else if (file.getBusinessCode() == FileBusinessType.USER) {
                userFiles.add(entry);
            }
        }

        projectIndexJsonCodec.complete(
                index,
                projectFiles,
                userFiles,
                files.size(),
                failNodes
        );
        objectStorageService.putObject(
                indexLocation,
                projectIndexJsonCodec.serialize(index),
                "application/json"
        );
    }

    private ObjectNode downloadProjectIndex(StorageLocation indexLocation) {
        String readUrl = objectStorageService.createReadUrl(indexLocation);
        byte[] content = REST_CLIENT.get()
                .uri(URI.create(readUrl))
                .retrieve()
                .body(byte[].class);
        return projectIndexJsonCodec.deserialize(content);
    }

    private boolean isFailedFile(ProjectFile file) {
        return file.getUploadStatus() == ProjectFileUploadStatus.NOT_UPLOADED
                || file.getStatus() == ProjectFileStatus.UPLOAD_FAILED
                || file.getStatus() == ProjectFileStatus.VERIFY_REQUIRED;
    }

    private boolean isActiveFile(ProjectFile file) {
        return file.getStatus() == ProjectFileStatus.ACTIVE
                && (file.getUploadStatus() == null
                || file.getUploadStatus() == ProjectFileUploadStatus.SUCCESS);
    }
}
