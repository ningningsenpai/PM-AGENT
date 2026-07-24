package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;

/**
 * LongTermMemory 表示写入 system/long_term_memory.json 的完整长期记忆。
 *
 * @author ning
 * @date 2026-07-24
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record LongTermMemory(
        Long projectId,
        String schemaVersion,
        String updatedAt,
        List<Memory> longTermMemory,
        List<Change> changes,
        List<IgnoredItem> ignoredItems
) {

    public static final String SCHEMA_VERSION = "1.0.0";

    public static LongTermMemory empty(Long projectId, String updatedAt) {
        return new LongTermMemory(
                projectId,
                SCHEMA_VERSION,
                updatedAt,
                List.of(),
                List.of(),
                List.of()
        );
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Memory(
            String id,
            String category,
            String title,
            String memory,
            String scope,
            String status,
            String confidence,
            String importance,
            List<String> tags,
            List<SourceRef> sourceRefs,
            List<Evidence> evidence,
            List<String> relatedSpecs,
            List<RelatedFile> relatedFiles,
            List<PreviousVersion> previousVersions,
            String createdAt,
            String updatedAt
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SourceRef(
            String type,
            String path,
            String section
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Evidence(
            String source,
            String quote
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RelatedFile(
            String path,
            String relation
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record PreviousVersion(
            String memory,
            String reason
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Change(
            String changeId,
            String changeType,
            String targetId,
            String summary,
            String createdAt
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record IgnoredItem(
            String content,
            String reason
    ) {
    }
}
