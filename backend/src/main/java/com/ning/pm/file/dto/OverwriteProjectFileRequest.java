package com.ning.pm.file.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import lombok.Getter;
import lombok.Setter;
import org.springframework.web.multipart.MultipartFile;

/**
 * OverwriteProjectFileRequest 定义覆盖文件内容所需参数。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
public class OverwriteProjectFileRequest {

    @NotNull(message = "源文件修改时间不能为空")
    @PositiveOrZero(message = "源文件修改时间不能小于0")
    private Long sourceMtimeMs;

    @NotNull(message = "乐观锁版本不能为空")
    @PositiveOrZero(message = "乐观锁版本不能小于0")
    private Integer lockVersion;

    @NotNull(message = "上传文件不能为空")
    private MultipartFile file;
}
