package com.ning.pm.file.dto;

import com.ning.pm.file.enums.FileBusinessType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import lombok.Getter;
import lombok.Setter;
import org.springframework.web.multipart.MultipartFile;

/**
 * CreateProjectFileRequest 定义单个项目文件上传参数。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
public class CreateProjectFileRequest {

    @Positive(message = "文件导入批次 ID 必须大于0")
    private Long ingestBatchId;

    @NotNull(message = "文件业务类型不能为空")
    private FileBusinessType businessCode;

    @NotBlank(message = "文件相对路径不能为空")
    private String relativePath;

    @NotNull(message = "源文件修改时间不能为空")
    @PositiveOrZero(message = "源文件修改时间不能小于0")
    private Long sourceMtimeMs;

    @NotNull(message = "上传文件不能为空")
    private MultipartFile file;
}
