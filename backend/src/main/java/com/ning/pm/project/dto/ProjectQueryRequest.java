package com.ning.pm.project.dto;

/**
 * ProjectQueryRequest 表示项目列表查询条件。
 *
 * @author ning
 * @date 2026-06-10
 */
public record ProjectQueryRequest(
        String status,
        String keyword
) {
}
