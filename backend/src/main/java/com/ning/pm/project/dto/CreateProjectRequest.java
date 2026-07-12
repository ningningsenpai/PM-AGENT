package com.ning.pm.project.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * CreateProjectRequest 定义创建项目文件归属空间的请求。
 *
 * @author ning
 * @date 2026-07-12
 */
public record CreateProjectRequest(
        @NotBlank(message = "项目名称不能为空")
        @Size(max = 128, message = "项目名称长度不能超过128个字符")
        String projectName
) {
}
