package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;

/**
 * ShortTermMemory 表示写入 system/short_term_memory.json 的完整短期记忆。
 *
 * @author ning
 * @date 2026-07-24
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ShortTermMemory(
        Long projectId,
        String schemaVersion,
        String updatedAt,
        List<Memory> shortTermMemory,
        List<PromotionCandidate> promotionCandidates,
        List<Change> changes,
        List<IgnoredItem> ignoredItems
) {

    public static final String SCHEMA_VERSION = "1.0.0";

    public static ShortTermMemory empty(Long projectId, String updatedAt) {
        return new ShortTermMemory(
                projectId,
                SCHEMA_VERSION,
                updatedAt,
                List.of(),
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
            String ttlHint,
            String nextCheck,
            boolean promoteCandidate,
            List<String> tags,
            List<SourceRef> sourceRefs,
            List<RelatedFile> relatedFiles,
            List<Evidence> evidence,
            String createdAt,
            String updatedAt
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SourceRef(
            String type,
            String summary
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RelatedFile(
            String path,
            String relation
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Evidence(
            String source,
            String quote
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record PromotionCandidate(
            String sourceMemoryId,
            String targetType,
            String reason,
            String status
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
