package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileChangeAction;
import com.ning.pm.file.enums.FileUploadItemStatus;
import lombok.Getter;
import lombok.Setter;

/**
 * ProjectFileUploadItem 保存覆盖写所需的新元信息和处理结果。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@TableName("pm_project_file_upload_item")
public class ProjectFileUploadItem extends BaseEntity {

    private Long uploadId;
    private Long fileId;
    private String relativePath;
    private String quickFingerprint;
    private String contentHash;
    private Long sizeBytes;
    private String contentType;
    private Long sourceMtimeMs;
    private FileChangeAction action;
    private FileUploadItemStatus status;
    private String errorMessage;
}
