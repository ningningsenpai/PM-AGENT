package com.ning.pm.project.context;

/**
 * ProjectScanSummary 保存筛选阶段的只读统计，索引构建不会借此修改业务数据。
 *
 * @author ning
 * @date 2026-07-15
 */
public record ProjectScanSummary(
        long totalNodes,
        long ignoredNodes,
        long skippedHashFiles,
        long scanErrorNodes
) {

    public static ProjectScanSummary fromStoredFiles(long storedFiles) {
        return new ProjectScanSummary(storedFiles, 0, 0, 0);
    }
}
