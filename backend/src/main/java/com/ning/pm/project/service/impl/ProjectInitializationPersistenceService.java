package com.ning.pm.project.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.repository.ProjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 将项目初始化的数据库步骤与 MinIO I/O 分离，避免外部调用占用数据库事务。
 * 封装部分非事务操作，提升业务代码可读性。
 */
@Service
@RequiredArgsConstructor
public class ProjectInitializationPersistenceService {

    private final ProjectMapper projectMapper;

    // 初始化项目，状态为 INITIALIZING
    @Transactional
    public void insertInitializing(Project project) {
        projectMapper.insert(project);
    }

    // INITIALIZING -> ACTIVE
    @Transactional
    public boolean markInitToActive(Long projectId) {
        return projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .eq(Project::getStatus, ProjectStatus.INITIALIZING)
                .set(Project::getStatus, ProjectStatus.ACTIVE)) > 0;
    }

    // INIT_FAILED -> ACTIVE
    @Transactional
    public boolean markInitFailedToActive(Long projectId) {
        return projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .eq(Project::getStatus, ProjectStatus.INIT_FAILED)
                .set(Project::getStatus, ProjectStatus.ACTIVE)) > 0;
    }

    // MinIo 初始化成功 && markActive失败 -> 标记项目失败后续触发新的上传逻辑(仅重试markActive)
    @Transactional
    public void markInitFailed(Long projectId) {
        projectMapper.update(null, new LambdaUpdateWrapper<Project>()
                .eq(Project::getId, projectId)
                .eq(Project::getStatus, ProjectStatus.INITIALIZING)
                .set(Project::getStatus, ProjectStatus.INIT_FAILED));
    }

    // MinIo 初始化失败 -> 直接删除项目记录
    @Transactional
    public void deleteProject(Long projectId) {
        projectMapper.deleteById(projectId);
    }

    // 根据 ownerUserId projectName 查询项目
    public Project checkProject(Long userId, String projectName) {
        return projectMapper.selectOne(new LambdaQueryWrapper<Project>()
                .eq(Project::getOwnerUserId, userId)
                .eq(Project::getProjectName, projectName));
    }
}
