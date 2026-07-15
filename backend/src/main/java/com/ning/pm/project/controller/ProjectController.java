package com.ning.pm.project.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.service.ProjectService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * ProjectController 提供项目创建、查询和硬删除接口。
 *
 * @author ning
 * @date 2026-07-12
 */
@RestController
@RequestMapping("/api/v1/projects")
@Slf4j
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectService projectService;

    /** 创建当前用户的项目文件空间。 */
    @SaCheckLogin
    @PostMapping
    public R<ProjectResponse> create(@Valid @RequestBody CreateProjectRequest request) {
        log.info("开始创建项目文件空间 projectName={}", request.projectName());
        ProjectResponse response = projectService.createProject(request);
        log.info("项目文件空间创建成功 projectId={}", response.id());
        return R.success(response);
    }

    /** 查询当前用户的项目文件空间。 */
    @SaCheckLogin
    @GetMapping
    public R<List<ProjectResponse>> list() {
        log.info("开始查询当前用户项目文件空间");
        List<ProjectResponse> response = projectService.listCurrentUserProjects();
        log.info("当前用户项目文件空间查询完成 count={}", response.size());
        return R.success(response);
    }

    /** 硬删除项目数据库记录及项目根前缀下的全部对象。 */
    @SaCheckLogin
    @DeleteMapping("/{projectId}")
    public R<Void> delete(@PathVariable Long projectId) {
        log.info("开始硬删除项目 projectId={}", projectId);
        projectService.deleteProject(projectId);
        log.info("项目硬删除成功 projectId={}", projectId);
        return R.success(null);
    }
}
