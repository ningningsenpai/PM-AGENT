package com.ning.pm.file.dto.parse;

/**
 * FileAnalysisResult 表示 Python 对单个文件返回的分析结果。
 */
public record FileAnalysisResult(
        Long projectId,
        Long fileId,
        String contentHash,
        String analysisVersion,
        String status,
        FileDetail detail,
        String errorCode,
        String errorMessage
) {
}
