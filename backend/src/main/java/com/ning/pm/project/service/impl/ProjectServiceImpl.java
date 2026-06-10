package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.project.converter.ProjectConverter;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectMember;
import com.ning.pm.project.domain.ProjectRole;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectQueryRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.dto.UpdateProjectRequest;
import com.ning.pm.project.dto.UpdateProjectStatusRequest;
import com.ning.pm.project.repository.ProjectMapper;
import com.ning.pm.project.repository.ProjectMemberMapper;
import com.ning.pm.project.service.ProjectService;
import com.ning.pm.task.domain.Task;
import com.ning.pm.task.repository.TaskMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ProjectServiceImpl 实现项目管理基础业务能力。
 *
 * @author ning
 * @date 2026-06-10
 */
@Service
public class ProjectServiceImpl implements ProjectService {

    private static final Logger log = LoggerFactory.getLogger(ProjectServiceImpl.class);
    private static final long DEFAULT_TENANT_ID = 0L;

    private final ProjectMapper projectMapper;
    private final ProjectMemberMapper projectMemberMapper;
    private final TaskMapper taskMapper;
    private final ProjectConverter projectConverter;
    private final CurrentUserHolder currentUserHolder;

    public ProjectServiceImpl(ProjectMapper projectMapper,
                              ProjectMemberMapper projectMemberMapper,
                              TaskMapper taskMapper,
                              ProjectConverter projectConverter,
                              CurrentUserHolder currentUserHolder) {
        this.projectMapper = projectMapper;
        this.projectMemberMapper = projectMemberMapper;
        this.taskMapper = taskMapper;
        this.projectConverter = projectConverter;
        this.currentUserHolder = currentUserHolder;
    }

    /** 创建项目，并把当前用户登记为项目负责人。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public ProjectResponse createProject(CreateProjectRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Project project = projectConverter.toEntity(request);
        project.setTenantId(DEFAULT_TENANT_ID);
        project.setOwnerId(userId);
        project.setStatus(ProjectStatus.NOT_STARTED.getCode());
        project.setDeleted(0);
        projectMapper.insert(project);

        ProjectMember member = new ProjectMember();
        member.setTenantId(DEFAULT_TENANT_ID);
        member.setProjectId(project.getId());
        member.setUserId(userId);
        member.setProjectRole(ProjectRole.OWNER.getCode());
        member.setJoinedAt(LocalDateTime.now());
        member.setDeleted(0);
        projectMemberMapper.insert(member);

        log.info("创建项目成功 projectId={}, ownerId={}", project.getId(), userId);
        return projectConverter.toResponse(project);
    }

    @Override
    public List<ProjectResponse> listProjects(ProjectQueryRequest request) {
        Long userId = currentUserHolder.requireUserId();
        LambdaQueryWrapper<Project> wrapper = new LambdaQueryWrapper<Project>()
                .eq(Project::getTenantId, DEFAULT_TENANT_ID)
                .and(scope -> scope.eq(Project::getOwnerId, userId)
                        .or()
                        .inSql(Project::getId, "select project_id from pm_project_member where tenant_id = 0 and deleted = 0 and user_id = " + userId));
        if (request.status() != null && !request.status().isBlank()) {
            if (!ProjectStatus.isValid(request.status())) {
                throw new BizException(ErrorCode.PROJECT_STATUS_INVALID);
            }
            wrapper.eq(Project::getStatus, request.status());
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String keyword = request.keyword().trim();
            wrapper.and(condition -> condition.like(Project::getName, keyword).or().like(Project::getCode, keyword));
        }
        wrapper.orderByDesc(Project::getUpdatedAt);
        return projectMapper.selectList(wrapper).stream()
                .map(projectConverter::toResponse)
                .toList();
    }

    @Override
    public ProjectResponse getProjectDetail(Long id) {
        Long userId = currentUserHolder.requireUserId();
        return projectConverter.toResponse(requireAccessibleProject(id, userId));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ProjectResponse updateProject(Long id, UpdateProjectRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Project project = requireAccessibleProject(id, userId);
        projectConverter.updateEntity(project, request);
        projectMapper.updateById(project);
        log.info("修改项目基础信息 projectId={}, operatorId={}", id, userId);
        return projectConverter.toResponse(project);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ProjectResponse updateProjectStatus(Long id, UpdateProjectStatusRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Project project = requireAccessibleProject(id, userId);
        if (!ProjectStatus.isValid(request.status())) {
            throw new BizException(ErrorCode.PROJECT_STATUS_INVALID);
        }
        String fromStatus = project.getStatus();
        project.setStatus(request.status());
        projectMapper.updateById(project);
        log.info("项目状态变更 projectId={}, fromStatus={}, toStatus={}, operatorId={}", id, fromStatus, request.status(), userId);
        return projectConverter.toResponse(project);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteProject(Long id) {
        Long userId = currentUserHolder.requireUserId();
        requireAccessibleProject(id, userId);
        projectMapper.deleteById(id);
        projectMemberMapper.delete(new LambdaQueryWrapper<ProjectMember>()
                .eq(ProjectMember::getTenantId, DEFAULT_TENANT_ID)
                .eq(ProjectMember::getProjectId, id));
        taskMapper.delete(new LambdaQueryWrapper<Task>()
                .eq(Task::getTenantId, DEFAULT_TENANT_ID)
                .eq(Task::getProjectId, id));
        log.info("逻辑删除项目 projectId={}, operatorId={}", id, userId);
    }

    @Override
    public Project requireAccessibleProject(Long projectId, Long userId) {
        Project project = projectMapper.selectById(projectId);
        if (project == null || Integer.valueOf(1).equals(project.getDeleted()) || !canAccessProject(projectId, userId, project)) {
            throw new BizException(ErrorCode.PROJECT_NOT_FOUND);
        }
        return project;
    }

    private boolean canAccessProject(Long projectId, Long userId, Project project) {
        if (userId.equals(project.getOwnerId())) {
            return true;
        }
        Long count = projectMemberMapper.selectCount(new LambdaQueryWrapper<ProjectMember>()
                .eq(ProjectMember::getTenantId, DEFAULT_TENANT_ID)
                .eq(ProjectMember::getProjectId, projectId)
                .eq(ProjectMember::getUserId, userId));
        return count != null && count > 0;
    }
}
