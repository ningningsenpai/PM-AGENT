package com.ning.pm.file.dto.file;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.Setter;
import org.springframework.web.multipart.MultipartFile;

@Getter
@Setter
public class UploadProjectFileRequest {

    @NotBlank(message = "文件相对路径不能为空")
    @Size(max = 512, message = "文件相对路径不能超过512个字符")
    private String relativePath;

    @NotNull(message = "源文件修改时间不能为空")
    @PositiveOrZero(message = "源文件修改时间不能小于0")
    private Long sourceMtimeMs;

    @NotNull(message = "上传文件不能为空")
    private MultipartFile file;
}
