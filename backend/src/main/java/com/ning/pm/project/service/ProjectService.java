package com.ning.pm.project.service;

import com.ning.pm.project.domain.Project;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectQueryRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.dto.UpdateProjectRequest;
import com.ning.pm.project.dto.UpdateProjectStatusRequest;

import java.util.List;

/**
 * ProjectService 提供项目管理基础业务能力。
 *
 * @author ning
 * @date 2026-06-10
 */
public interface ProjectService {

    ProjectResponse createProject(CreateProjectRequest request);

    List<ProjectResponse> listProjects(ProjectQueryRequest request);

    ProjectResponse getProjectDetail(Long id);

    ProjectResponse updateProject(Long id, UpdateProjectRequest request);

    ProjectResponse updateProjectStatus(Long id, UpdateProjectStatusRequest request);

    void deleteProject(Long id);

    Project requireAccessibleProject(Long projectId, Long userId);
}
