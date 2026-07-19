package com.ning.pm.file.dto.file;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

/**
 * UpdateProjectFilePathRequest 定义文件移动或重命名参数。
 *
 * @author ning
 * @date 2026-07-12
 */
public record UpdateProjectFilePathRequest(
        @NotBlank(message = "文件相对路径不能为空")
        String relativePath,
        @NotNull(message = "源文件修改时间不能为空")
        @PositiveOrZero(message = "源文件修改时间不能小于0")
        Long sourceMtimeMs,
        @NotNull(message = "乐观锁版本不能为空")
        @PositiveOrZero(message = "乐观锁版本不能小于0")
        Integer lockVersion
) {
}
