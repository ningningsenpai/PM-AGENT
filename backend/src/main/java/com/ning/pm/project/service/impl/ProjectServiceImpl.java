package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
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
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

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
    private final PlatformTransactionManager transactionManager;
    private final ProjectInitializationPersistenceService initializationPersistenceService;

    @Override
    public ProjectResponse createProject(CreateProjectRequest request) {
        Project project = projectConverter.toEntity(request);
        project.setProjectName(request.projectName().trim());
        project.setOwnerUserId(currentUserHolder.requireUserId());
        project.setStatus(ProjectStatus.INITIALIZING);
        initializationPersistenceService.insertInitializing(project);
        try {
            projectIndexService.initialize(project);
        } catch (RuntimeException exception) {
            try {
                initializationPersistenceService.markInitFailed(project.getId());
            } catch (RuntimeException persistenceException) {
                exception.addSuppressed(persistenceException);
            }
            throw exception;
        }
        if (!initializationPersistenceService.markActive(project.getId())) {
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
        Project project = requireOwnedProjectForDelete(projectId);
        claimProjectForDelete(project);
        try {
            objectStorageService.removeByPrefix(locationFactory.buildProjectPrefix(
                    project.getOwnerUserId(),
                    project.getId()
            ));
        } catch (RuntimeException exception) {
            markProjectDeleteFailed(project.getId());
            throw new SystemException(
                    ErrorCode.PROJECT_DELETE_FAILED,
                    "项目对象未能全部删除",
                    exception
            );
        }

        try {
            TransactionTemplate transactionTemplate = new TransactionTemplate(transactionManager);
            transactionTemplate.executeWithoutResult(status -> {
                projectFileMapper.delete(new LambdaQueryWrapper<ProjectFile>()
                        .eq(ProjectFile::getProjectId, project.getId()));
                int deleted = projectMapper.deleteById(project.getId());
                if (deleted == 0) {
                    throw new SystemException(ErrorCode.PROJECT_DELETE_FAILED, "项目记录硬删除失败");
                }
            });
        } catch (RuntimeException exception) {
            markProjectDeleteFailed(project.getId());
            if (exception instanceof SystemException systemException
                    && systemException.getErrorCode() == ErrorCode.PROJECT_DELETE_FAILED) {
                throw systemException;
            }
            throw new SystemException(
                    ErrorCode.PROJECT_DELETE_FAILED,
                    "项目数据库记录硬删除失败",
                    exception
            );
        }
    }

    private Project requireOwnedProjectForDelete(Long projectId) {
        Project project = projectMapper.selectById(projectId);
        Long userId = currentUserHolder.requireUserId();
        if (project == null || !userId.equals(project.getOwnerUserId())) {
            throw new BizException(ErrorCode.PROJECT_NOT_FOUND);
        }
        boolean deletable = project.getStatus() == ProjectStatus.ACTIVE
                || project.getStatus() == ProjectStatus.INIT_FAILED
                || project.getStatus() == ProjectStatus.DELETING
                || project.getStatus() == ProjectStatus.DELETE_FAILED;
        if (!deletable) {
            throw new BizException(ErrorCode.PROJECT_DISABLED);
        }
        return project;
    }

    private void claimProjectForDelete(Project project) {
        int updated = projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, project.getId())
                .in(Project::getStatus,
                        ProjectStatus.ACTIVE,
                        ProjectStatus.INIT_FAILED,
                        ProjectStatus.DELETING,
                        ProjectStatus.DELETE_FAILED)
                .set(Project::getStatus, ProjectStatus.DELETING));
        if (updated == 0) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "项目正在被其他请求处理");
        }
    }

    private void markProjectDeleteFailed(Long projectId) {
        projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .set(Project::getStatus, ProjectStatus.DELETE_FAILED));
    }
}
