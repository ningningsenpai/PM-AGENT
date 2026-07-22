package com.ning.pm.file.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ning.pm.file.converter.ParseFileDataConverter;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * ParseFileDataFactory 负责为文件解析服务组装 Python 接口请求数据。
 * @author ning
 * @date 2026-07-22
 */
@Component
@RequiredArgsConstructor
public class ParseFileDataFactory {

    private final ProjectService projectService;
    private final ProjectFileMapper projectFileMapper;
    private final ParseFileDataConverter parseFileDataConverter;
    private final ProjectFileService projectFileService;

    /**
     * 查询项目内可解析文件，并转换为 Python 文件分析请求。
     */
    public List<FileAnalysisRequest> getInitParseData(Long projectId) {
        Project project = projectService.requireOwnedProject(projectId);
        return projectFileMapper.selectList(new LambdaQueryWrapper<ProjectFile>()
                        .eq(ProjectFile::getProjectId, projectId)
                        .eq(ProjectFile::getParseAttempts, 0)
                        .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                        .ne(ProjectFile::getBusinessCode, FileBusinessType.SYSTEM)
                        .orderByAsc(ProjectFile::getRelativePath))
                .stream()
                .map(file -> generateParameters(project, file))
                .toList();
    }


    /** 执行类型转换以及参数补全 */
    private FileAnalysisRequest generateParameters(Project project, ProjectFile file) {
        String fileUrl = projectFileService.createReadUrl(file.getProjectId(), file.getId()).url();
        String storageName = file.getStorageName();
        int extensionIndex = storageName.lastIndexOf('.');
        String detailName = extensionIndex > 0 ? storageName.substring(0, extensionIndex) : storageName;
        String detailRef = "system/file_details/" + detailName + ".json";
        String analysisVersion = "file-detail-v1";
        return parseFileDataConverter.toFileAnalysisRequest(
                file, project.getOwnerUserId(), fileUrl, detailRef, analysisVersion);
    }

}
