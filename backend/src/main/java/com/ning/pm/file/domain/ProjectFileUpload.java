package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.FileUploadSource;
import com.ning.pm.file.enums.FileUploadStatus;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * ProjectFileUpload 记录一次文件上传或覆盖操作。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@TableName("pm_project_file_upload")
public class ProjectFileUpload extends BaseEntity {

    private Long projectId;
    private FileBusinessType businessCode;
    private FileUploadSource source;
    private FileUploadStatus status;
    private String idempotencyKey;
    private Integer totalFiles;
    private Integer uploadedFiles;
    private Integer skippedFiles;
    private Integer failedFiles;
    private LocalDateTime startedAt;
    private LocalDateTime completedAt;
}
