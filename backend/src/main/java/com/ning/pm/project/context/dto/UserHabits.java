package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;

/**
 * UserHabits 表示写入 system/user_habits/{category}.json 的单类用户习惯。
 *
 * @author ning
 * @date 2026-07-24
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record UserHabits(
        Long projectId,
        String schemaVersion,
        String category,
        String updatedAt,
        List<Habit> userHabits,
        List<Change> changes,
        List<IgnoredItem> ignoredItems
) {

    public static final String SCHEMA_VERSION = "1.0.0";
    public static final String CATEGORY_WORK = "work";
    public static final String CATEGORY_LIFE = "life";
    public static final String CATEGORY_THINKING = "thinking";
    public static final String CATEGORY_SPECIFICATION = "specification";
    public static final String CATEGORY_TOOLING = "tooling";
    public static final List<String> CATEGORIES = List.of(
            CATEGORY_WORK,
            CATEGORY_LIFE,
            CATEGORY_THINKING,
            CATEGORY_SPECIFICATION,
            CATEGORY_TOOLING
    );

    public static UserHabits empty(Long projectId, String category, String updatedAt) {
        if (!CATEGORIES.contains(category)) {
            throw new IllegalArgumentException("用户习惯分类不合法");
        }
        return new UserHabits(
                projectId,
                SCHEMA_VERSION,
                category,
                updatedAt,
                List.of(),
                List.of(),
                List.of()
        );
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Habit(
            String id,
            String title,
            String habit,
            String scope,
            String status,
            String confidence,
            String importance,
            List<String> tags,
            List<String> signals,
            String sourceType,
            List<SourceRef> sourceRefs,
            List<String> applicableScenarios,
            List<String> avoidWhen,
            String changeType,
            List<PreviousVersion> previousVersions,
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
    public record PreviousVersion(
            String habit,
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
            String contentSummary,
            String reason
    ) {
    }
}
