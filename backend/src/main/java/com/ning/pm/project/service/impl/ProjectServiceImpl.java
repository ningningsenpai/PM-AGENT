package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
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
 * ProjectServiceImpl 提供文件模块所需的最小项目归属与所有权校验能力。
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

    @Override
    public ProjectResponse createProject(CreateProjectRequest request) {
        Project project = projectConverter.toEntity(request);
        project.setProjectName(request.projectName().trim());
        project.setOwnerUserId(currentUserHolder.requireUserId());
        project.setStatus(ProjectStatus.ACTIVE);
        projectMapper.insert(project);
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
}
