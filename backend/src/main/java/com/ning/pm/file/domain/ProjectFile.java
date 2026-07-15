package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import lombok.Getter;
import lombok.Setter;

/**
 * ProjectFile 表示具有稳定对象键的项目逻辑文件。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@TableName("pm_project_file")
public class ProjectFile extends BaseEntity {

    private Long projectId;
    private FileBusinessType businessCode;
    private String relativePath;
    private String pathHash;
    private String fileName;
    private String extension;
    private String storageUuid;
    private String objectKey;
    private String contentType;
    private Long sizeBytes;
    private Long sourceMtimeMs;
    private String quickFingerprint;
    private String contentHash;
    private ProjectFileStatus status;
    private Integer uploadAttempts;
    private String lastErrorCode;
    private String lastErrorMessage;
    private java.time.LocalDateTime lastFailedAt;
    private Integer lockVersion;
}
