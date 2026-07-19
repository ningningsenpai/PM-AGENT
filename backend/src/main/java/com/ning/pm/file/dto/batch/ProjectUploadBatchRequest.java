package com.ning.pm.file.dto.batch;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.ning.pm.file.enums.FileBusinessType;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ProjectUploadBatchRequest(
        @NotNull(message = "用户ID不能为空")
        @Positive(message = "用户ID必须大于0")
        Long userId,

        @NotNull(message = "项目ID不能为空")
        @Positive(message = "项目ID必须大于0")
        Long projectId,

        @NotBlank(message = "请求ID不能为空")
        @Size(max = 64, message = "请求ID不能超过64个字符")
        String requestId,

        @NotNull(message = "上传轮次不能为空")
        @Min(value = 1, message = "上传轮次不能小于1")
        @Max(value = 3, message = "上传最多执行三轮")
        Integer attemptNo,

        @NotBlank(message = "批次ID不能为空")
        @Size(max = 64, message = "批次ID不能超过64个字符")
        String batchId,

        @NotBlank(message = "幂等键不能为空")
        @Size(max = 64, message = "幂等键不能超过64个字符")
        String idempotencyKey,

        @NotNull(message = "批次文件数不能为空")
        @Min(value = 1, message = "批次文件数不能小于1")
        @Max(value = 50, message = "单批次最多包含50个文件")
        Integer fileCount,

        @NotEmpty(message = "文件信息列表不能为空")
        @Size(max = 50, message = "单批次最多包含50个文件")
        List<@Valid FileDescriptor> files
) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FileDescriptor(
            @NotBlank(message = "文件ID不能为空")
            @Size(max = 128, message = "文件ID不能超过128个字符")
            String clientFileId,

            FileBusinessType businessCode,

            @NotBlank(message = "文件相对路径不能为空")
            @Size(max = 512, message = "文件相对路径不能超过512个字符")
            String relativePath,

            @NotBlank(message = "文件名不能为空")
            @Size(max = 255, message = "文件名不能超过255个字符")
            String fileName,

            @NotNull(message = "文件大小不能为空")
            @PositiveOrZero(message = "文件大小不能小于0")
            Long sizeBytes,

            @NotNull(message = "源文件修改时间不能为空")
            @PositiveOrZero(message = "源文件修改时间不能小于0")
            Long sourceMtimeMs
    ) {
    }
}
