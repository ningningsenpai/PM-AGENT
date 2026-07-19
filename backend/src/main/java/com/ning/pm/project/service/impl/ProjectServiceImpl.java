package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.converter.ProjectConverter;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.repository.ProjectMapper;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * ProjectServiceImpl 编排项目归属、初始上下文索引和项目硬删除生命周期。
 *
 * @author ning
 * @date 2026-07-12
 */
@Service
@RequiredArgsConstructor
public class ProjectServiceImpl implements ProjectService {

    private final ProjectMapper projectMapper;
    private final ProjectConverter projectConverter;
    private final CurrentUserHolder currentUserHolder;
    private final ProjectFileMapper projectFileMapper;
    private final ProjectIndexService projectIndexService;
    private final FileStorageLocationFactory locationFactory;
    private final ObjectStorageService objectStorageService;
    private final ProjectInitializationPersistenceService initializationPersistenceService;

    @Override
    public ProjectResponse createProject(CreateProjectRequest request) {
        Project oldProject = initializationPersistenceService.checkProject(
                currentUserHolder.requireUserId(),
                request.projectName().trim());
        if (oldProject != null) {
            // 项目存在且状态为 active -> 更改项目名称
            if(oldProject.getStatus().equals(ProjectStatus.ACTIVE)) {
                throw new BizException(ErrorCode.PROJECT_NAME_EXISTS, "项目名称已存在");
            }
            // 项目存在且状态为 init_failed -> 重新初始化 index.json 后再激活
            if(oldProject.getStatus().equals(ProjectStatus.INIT_FAILED)) {
                projectIndexService.initialize(oldProject);
                if (!initializationPersistenceService.markInitFailedToActive(oldProject.getId())) {
                    throw new SystemException(ErrorCode.PROJECT_INDEX_INIT_FAILED, "项目初始化状态落库失败");
                }
                oldProject.setStatus(ProjectStatus.ACTIVE);
                return projectConverter.toResponse(oldProject);
            }
        }
        // 项目不存在
        Project project = projectConverter.toEntity(request);
        project.setProjectName(request.projectName().trim());
        project.setOwnerUserId(currentUserHolder.requireUserId());
        project.setStatus(ProjectStatus.INITIALIZING);
        initializationPersistenceService.insertInitializing(project);
        try {
            projectIndexService.initialize(project);
        } catch (RuntimeException exception) {
            try {
                // TODO : 补充 idnex.json 初始化失败的校验和补偿机制
                initializationPersistenceService.deleteProject(project.getId());
            } catch (RuntimeException persistenceException) {
                exception.addSuppressed(persistenceException);
            }
            throw exception;
        }
        if (!initializationPersistenceService.markInitToActive(project.getId())) {
            initializationPersistenceService.markInitFailed(project.getId());
            throw new SystemException(ErrorCode.PROJECT_INDEX_INIT_FAILED, "项目初始化状态落库失败");
        }
        project.setStatus(ProjectStatus.ACTIVE);
        return projectConverter.toResponse(project);
    }

    @Override
    public List<ProjectResponse> listCurrentUserProjects() {
        Long userId = currentUserHolder.requireUserId();
        return projectMapper.selectList(new LambdaQueryWrapper<Project>()
                        .eq(Project::getOwnerUserId, userId)
                        .orderByDesc(Project::getCreatedAt))
                .stream()
                .map(projectConverter::toResponse)
                .toList();
    }

    /** 校验项目存在、属于当前用户且处于可用状态。 */
    @Override
    public Project requireOwnedProject(Long projectId) {
        Project project = projectMapper.selectById(projectId);
        Long userId = currentUserHolder.requireUserId();
        if (project == null || !userId.equals(project.getOwnerUserId())) {
            throw new BizException(ErrorCode.PROJECT_NOT_FOUND);
        }
        if (project.getStatus() != ProjectStatus.ACTIVE) {
            throw new BizException(ErrorCode.PROJECT_DISABLED);
        }
        return project;
    }

    /** 删除项目根前缀下的全部对象后，在独立数据库事务中硬删除项目数据。 */
    @Override
    public void deleteProject(Long projectId) {
        // 校验项目存在、属于当前用户且处于可用状态
        Project project = requireOwnedProject(projectId);
        // 校验项目根前缀下的全部对象是否存在
        try {
            objectStorageService.removeByPrefix(locationFactory.buildProjectPrefix(
                    project.getOwnerUserId(),
                    project.getId()
            ));
        } catch (RuntimeException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_DELETE_FAILED,
                    "项目对象未能全部删除",
                    exception
            );
        }

        // 删除 MySQL 数据库记录
        try {
            projectFileMapper.delete(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getProjectId, project.getId()));
            initializationPersistenceService.deleteProject(projectId);
        } catch (RuntimeException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_DELETE_FAILED,
                    "项目数据库记录硬删除失败",
                    exception
            );
        }
    }
}
