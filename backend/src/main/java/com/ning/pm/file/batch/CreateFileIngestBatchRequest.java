package com.ning.pm.file.batch;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

public record CreateFileIngestBatchRequest(
        @NotNull(message = "文件总数不能为空")
        @PositiveOrZero(message = "文件总数不能小于0")
        @Max(value = 100000, message = "单个导入批次不能超过100000个文件")
        Integer totalFiles
) {
}
