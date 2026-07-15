package com.ning.pm.project.dto;

import com.ning.pm.project.domain.ProjectStatus;

import java.time.LocalDateTime;

/**
 * ProjectResponse 返回项目文件归属空间的基础信息。
 *
 * @author ning
 * @date 2026-07-12
 */
public record ProjectResponse(
        Long id,
        String projectName,
        ProjectStatus status,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
