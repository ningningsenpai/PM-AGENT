package com.ning.pm.file.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.file.service.ProjectFileParseService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * ProjectFileParseController 提供项目文件解析接口。
 *
 * @author ning
 * @date 2026-07-22
 */
@RestController
@RequestMapping("/api/v1/projects/{projectId}/files")
@RequiredArgsConstructor
public class ProjectFileParseController {

    private final ProjectFileParseService projectFileParseService;

    /** 触发项目文件解析。 */
    @SaCheckLogin
    @PostMapping("/parse/init")
    public R<Void> initParse(@PathVariable Long projectId) {
        projectFileParseService.initParseFiles(projectId);
        return R.success(null);
    }
}
