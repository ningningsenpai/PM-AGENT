package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ProjectIndex 表示写入 system/index.json 的完整项目上下文索引。
 *
 * @author ning
 * @date 2026-07-15
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ProjectIndex(
        Long projectId,
        String projectName,
        Long ownerUserId,
        String schemaVersion,
        LocalDateTime generatedAt,
        LocalDateTime updatedAt,
        Storage storage,
        Summary summary,
        List<FileEntry> project,
        List<FileEntry> user,
        List<UploadFailure> uploadFailures,
        SystemSection system
) {

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Storage(
            String provider,
            String bucket,
            String objectPrefix,
            String indexPath
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Summary(
            long totalNodes,
            long activeFiles,
            long failNodes
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record FileEntry(
            Long id,
            String storageUuid,
            String logicalPath,
            String fileName,
            String storageName,
            String minioPath,
            Long sizeBytes,
            String contentType,
            String status,
            String analysisStatus,
            String quickFingerprint,
            String contentHash,
            String module,
            String kind,
            String language,
            String importance,
            String summary,
            List<String> keywords,
            String detailRef,
            LocalDateTime updatedAt
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record UploadFailure(
            Long fileId,
            String business,
            String logicalPath,
            String fileName,
            String storageName,
            String status,
            Integer attempts,
            String lastErrorCode,
            LocalDateTime updatedAt
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SystemSection(
            String index,
            String fileDetails,
            String projectSpecification,
            String longTermMemory,
            String shortTermMemory,
            String userHabits,
            String updateJournal
    ) {
    }
}
