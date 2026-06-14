package com.ning.pm.task.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * UpdateTaskStatusRequest 表示任务状态切换请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record UpdateTaskStatusRequest(
        @NotBlank(message = "任务状态不能为空")
        String status,

        @Size(max = 255, message = "状态变更原因长度不能超过 255 个字符")
        String reason
) {
}
