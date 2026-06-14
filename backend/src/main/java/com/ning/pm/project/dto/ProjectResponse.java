package com.ning.pm.project.dto;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * ProjectResponse 表示项目接口统一响应对象。
 *
 * @author ning
 * @date 2026-06-10
 */
public record ProjectResponse(
        Long id,
        Long tenantId,
        String name,
        String code,
        String description,
        Long ownerId,
        String status,
        LocalDate startDate,
        LocalDate endDate,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
