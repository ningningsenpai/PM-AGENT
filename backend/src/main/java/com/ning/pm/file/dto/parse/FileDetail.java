package com.ning.pm.file.dto.parse;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;

/**
 * FileDetail 表示 Python 返回并写入 system/file_details 的完整文件详情。
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record FileDetail(
        String id,
        Long projectId,
        Long fileId,
        String schemaVersion,
        String analysisVersion,
        String generatedAt,
        String updatedAt,
        String storageUuid,
        String storageName,
        String detailRef,
        String originalPath,
        String minioPath,
        Long sizeBytes,
        String contentType,
        String contentHash,
        String module,
        String kind,
        String fileType,
        String language,
        String status,
        String importance,
        String summary,
        List<String> keywords,
        String role,
        List<JsonNode> contentSlices,
        List<String> relatedTopics,
        List<JsonNode> relatedFiles,
        List<JsonNode> riskFlags,
        List<JsonNode> sensitiveFlags,
        List<JsonNode> evidence,
        List<JsonNode> previousVersions,
        JsonNode parser
) {
}
