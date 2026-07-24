package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.util.List;

/**
 * ProjectSpecification 表示写入 system/project_specification.json 的完整项目规范。
 *
 * @author ning
 * @date 2026-07-24
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ProjectSpecification(
        Long projectId,
        String schemaVersion,
        String updatedAt,
        Specification projectSpecification,
        List<Change> changes,
        List<IgnoredItem> ignoredItems
) {

    public static final String SCHEMA_VERSION = "1.0.0";

    public static ProjectSpecification empty(Long projectId, String updatedAt) {
        return new ProjectSpecification(
                projectId,
                SCHEMA_VERSION,
                updatedAt,
                new Specification(
                        new DevelopmentStage("", "", List.of(), List.of()),
                        List.of(),
                        List.of(),
                        List.of(),
                        List.of(),
                        List.of()
                ),
                List.of(),
                List.of()
        );
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Specification(
            DevelopmentStage developmentStage,
            List<DevelopmentApproach> developmentApproach,
            List<TechnicalConstraint> technicalConstraints,
            List<SpecificationRule> codingRules,
            List<SpecificationRule> documentRules,
            List<SpecificationRule> riskRules
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record DevelopmentStage(
            String currentStage,
            String stageGoal,
            List<String> completed,
            List<String> nextFocus
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record DevelopmentApproach(
            String id,
            String rule,
            String scope,
            String status,
            String confidence,
            List<SourceRef> sourceRefs,
            String createdAt,
            String updatedAt,
            List<JsonNode> previousVersions
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record TechnicalConstraint(
            String id,
            String constraint,
            String scope,
            String status,
            String confidence,
            List<SourceRef> sourceRefs,
            String createdAt,
            String updatedAt,
            List<JsonNode> previousVersions
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SpecificationRule(
            String id,
            String scope,
            String rule,
            String status,
            String confidence,
            List<SourceRef> sourceRefs,
            String createdAt,
            String updatedAt,
            List<JsonNode> previousVersions
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SourceRef(
            String type,
            String path
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
