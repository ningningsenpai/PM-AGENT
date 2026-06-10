package com.ning.pm.task.dto;

/**
 * TaskQueryRequest 表示任务列表查询条件。
 *
 * @author ning
 * @date 2026-06-10
 */
public record TaskQueryRequest(
        Long projectId,
        String status,
        Long assigneeId,
        String keyword
) {
}
