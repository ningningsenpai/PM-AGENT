package com.ning.pm.file.analysis.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 单文件完整详情文档。顶层索引投影字段与可按需读取的深层语义统一保存在同一对象中。
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record FileDetailDocument(
        @NotBlank @Size(max = 128) String id,
        @NotNull @Min(1) Long projectId,
        @NotNull @Min(1) Long fileId,
        @NotBlank @Size(max = 32) String schemaVersion,
        @NotBlank @Size(max = 64) String analysisVersion,
        @NotNull LocalDateTime generatedAt,
        @NotNull LocalDateTime updatedAt,
        @NotBlank @Size(max = 32) String storageUuid,
        @NotBlank @Size(max = 255) String storageName,
        @NotBlank @Size(max = 512) String detailRef,
        @NotBlank @Size(max = 512) String originalPath,
        @NotBlank @Size(max = 512) String minioPath,
        @NotNull @Min(0) Long sizeBytes,
        @NotBlank @Size(max = 128) String contentType,
        @NotBlank @Size(max = 80) String contentHash,
        @NotBlank @Size(max = 128) String module,
        @NotBlank @Size(max = 64) String kind,
        @NotBlank @Size(max = 128) String fileType,
        @NotBlank @Size(max = 32) String language,
        @NotBlank @Size(max = 32) String status,
        @NotBlank @Size(max = 16) String importance,
        @NotBlank @Size(max = 1000) String summary,
        @NotEmpty @Size(max = 32) List<@NotBlank @Size(max = 64) String> keywords,
        @NotBlank @Size(max = 1000) String role,
        @NotNull @Size(max = 64) List<@Valid ContentSlice> contentSlices,
        @NotNull @Size(max = 32) List<@NotBlank @Size(max = 128) String> relatedTopics,
        @NotNull @Size(max = 64) List<@Valid RelatedFile> relatedFiles,
        @NotNull @Size(max = 32) List<@NotBlank @Size(max = 128) String> riskFlags,
        @NotNull @Size(max = 32) List<@NotBlank @Size(max = 128) String> sensitiveFlags,
        @NotNull @Size(max = 32) List<@Valid Evidence> evidence,
        @NotNull @Size(max = 20) List<@Valid PreviousVersion> previousVersions,
        @NotNull @Valid ParserMetadata parser
) {

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ContentSlice(
            @NotBlank @Size(max = 128) String sliceId,
            @NotBlank @Size(max = 32) String type,
            @NotBlank @Size(max = 1000) String summary,
            @NotNull @Size(max = 20) List<@NotBlank @Size(max = 64) String> keywords,
            @NotNull @Size(max = 64) List<@NotBlank @Size(max = 256) String> entities,
            @Valid SourceRange sourceRange
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record SourceRange(
            @Min(1) int startLine,
            @Min(1) int endLine
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RelatedFile(
            @NotBlank @Size(max = 512) String path,
            @NotBlank @Size(max = 64) String relation
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record Evidence(
            @NotBlank @Size(max = 64) String source,
            @NotBlank @Size(max = 300) String quote
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record PreviousVersion(
            @NotBlank @Size(max = 80) String contentHash,
            @NotBlank @Size(max = 1000) String role,
            @NotNull LocalDateTime changedAt,
            @NotBlank @Size(max = 500) String reason
    ) {
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ParserMetadata(
            @NotBlank @Size(max = 64) String strategy,
            @NotBlank @Size(max = 128) String parserVersion,
            @NotNull Boolean sampled,
            @NotNull @Min(0) @Max(1000000) Integer parsedLines
    ) {
    }
}
