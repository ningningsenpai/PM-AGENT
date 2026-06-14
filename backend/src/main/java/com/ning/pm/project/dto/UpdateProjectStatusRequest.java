package com.ning.pm.project.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * UpdateProjectStatusRequest 表示修改项目状态请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record UpdateProjectStatusRequest(
        @NotBlank(message = "项目状态不能为空")
        String status
) {
}
