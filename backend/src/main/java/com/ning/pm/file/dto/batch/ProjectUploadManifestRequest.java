package com.ning.pm.file.dto.batch;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.ning.pm.file.enums.ProjectUploadExecutionStatus;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ProjectUploadManifestRequest(
        @NotNull(message = "用户ID不能为空")
        @Positive(message = "用户ID必须大于0")
        Long userId,

        @NotNull(message = "项目ID不能为空")
        @Positive(message = "项目ID必须大于0")
        Long projectId,

        @NotBlank(message = "请求ID不能为空")
        @Size(max = 64, message = "请求ID不能超过64个字符")
        String requestId,

        @NotNull(message = "执行状态不能为空")
        ProjectUploadExecutionStatus executionStatus,

        @NotNull(message = "上传轮次不能为空")
        @Min(value = 1, message = "上传轮次不能小于1")
        @Max(value = 3, message = "上传最多执行三轮")
        Integer attemptNo,

        @NotNull(message = "原始文件总数不能为空")
        @Positive(message = "原始文件总数必须大于0")
        Integer originalTotalFiles,

        @NotNull(message = "本轮文件总数不能为空")
        @Positive(message = "本轮文件总数必须大于0")
        Integer roundTotalFiles,

        @NotNull(message = "本轮批次总数不能为空")
        @Positive(message = "本轮批次总数必须大于0")
        Integer totalBatchCount,

        @NotEmpty(message = "批次摘要不能为空")
        List<@Valid BatchSummary> batches
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record BatchSummary(
            @NotBlank(message = "批次ID不能为空")
            @Size(max = 64, message = "批次ID不能超过64个字符")
            String batchId,

            @NotNull(message = "批次文件数不能为空")
            @Min(value = 1, message = "批次文件数不能小于1")
            @Max(value = 50, message = "单批次最多包含50个文件")
            Integer fileCount
    ) {
    }
}
