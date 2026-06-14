package com.ning.pm.project.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectQueryRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.dto.UpdateProjectRequest;
import com.ning.pm.project.dto.UpdateProjectStatusRequest;
import com.ning.pm.project.service.ProjectService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * ProjectController 提供第 1 阶段项目管理接口。
 *
 * @author ning
 * @date 2026-06-10
 */
@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {

    private final ProjectService projectService;

    public ProjectController(ProjectService projectService) {
        this.projectService = projectService;
    }

    /** 创建项目。 */
    @SaCheckLogin
    @PostMapping
    public R<ProjectResponse> createProject(@Valid @RequestBody CreateProjectRequest request) {
        return R.success(projectService.createProject(request));
    }

    /** 查询当前用户可见项目列表。 */
    @SaCheckLogin
    @GetMapping
    public R<List<ProjectResponse>> listProjects(@RequestParam(required = false) String status,
                                                 @RequestParam(required = false) String keyword) {
        return R.success(projectService.listProjects(new ProjectQueryRequest(status, keyword)));
    }

    /** 查询项目详情。 */
    @SaCheckLogin
    @GetMapping("/{id}")
    public R<ProjectResponse> getProjectDetail(@PathVariable Long id) {
        return R.success(projectService.getProjectDetail(id));
    }

    /** 修改项目基础信息。 */
    @SaCheckLogin
    @PutMapping("/{id}")
    public R<ProjectResponse> updateProject(@PathVariable Long id, @Valid @RequestBody UpdateProjectRequest request) {
        return R.success(projectService.updateProject(id, request));
    }

    /** 修改项目状态。 */
    @SaCheckLogin
    @PatchMapping("/{id}/status")
    public R<ProjectResponse> updateProjectStatus(@PathVariable Long id,
                                                  @Valid @RequestBody UpdateProjectStatusRequest request) {
        return R.success(projectService.updateProjectStatus(id, request));
    }

    /** 逻辑删除项目，并同步逻辑删除项目成员和项目任务。 */
    @SaCheckLogin
    @DeleteMapping("/{id}")
    public R<Void> deleteProject(@PathVariable Long id) {
        projectService.deleteProject(id);
        return R.success(null);
    }
}
