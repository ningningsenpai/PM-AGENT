package com.ning.pm.task.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * CreateTaskRequest 表示创建任务请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record CreateTaskRequest(
        @NotNull(message = "项目 ID 不能为空")
        Long projectId,

        @NotBlank(message = "任务标题不能为空")
        @Size(max = 255, message = "任务标题长度不能超过 255 个字符")
        String title,

        String description,

        Long assigneeId,

        String priority,

        LocalDate dueDate,

        @DecimalMin(value = "0.00", message = "预估工时不能小于 0")
        BigDecimal estimatedHours
) {
}
