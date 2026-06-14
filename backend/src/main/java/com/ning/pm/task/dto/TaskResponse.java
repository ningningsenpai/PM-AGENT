package com.ning.pm.task.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * TaskResponse 表示任务接口统一响应对象。
 *
 * @author ning
 * @date 2026-06-10
 */
public record TaskResponse(
        Long id,
        Long tenantId,
        Long projectId,
        String title,
        String description,
        Long assigneeId,
        String status,
        String priority,
        LocalDate dueDate,
        BigDecimal estimatedHours,
        BigDecimal actualHours,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
