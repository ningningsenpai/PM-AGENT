package com.ning.pm.project.service;

import com.ning.pm.project.domain.Project;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectResponse;

import java.util.List;

public interface ProjectService {

    ProjectResponse createProject(CreateProjectRequest request);

    List<ProjectResponse> listCurrentUserProjects();

    Project requireOwnedProject(Long projectId);
}
