package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.repository.ProjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 将项目初始化的数据库步骤与 MinIO I/O 分离，避免外部调用占用数据库事务。
 */
@Service
@RequiredArgsConstructor
public class ProjectInitializationPersistenceService {

    private final ProjectMapper projectMapper;

    @Transactional
    public void insertInitializing(Project project) {
        projectMapper.insert(project);
    }

    @Transactional
    public boolean markActive(Long projectId) {
        return projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .eq(Project::getStatus, ProjectStatus.INITIALIZING)
                .set(Project::getStatus, ProjectStatus.ACTIVE)) > 0;
    }

    @Transactional
    public void markInitFailed(Long projectId) {
        projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .eq(Project::getStatus, ProjectStatus.INITIALIZING)
                .set(Project::getStatus, ProjectStatus.INIT_FAILED));
    }
}
