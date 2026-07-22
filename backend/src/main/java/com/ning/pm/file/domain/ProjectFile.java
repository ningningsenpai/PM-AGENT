package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import lombok.Getter;
import lombok.Setter;

import java.util.List;

/**
 * ProjectFile 表示具有稳定对象键的项目逻辑文件。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@TableName(value = "pm_project_file", autoResultMap = true)
public class ProjectFile extends BaseEntity {

    private Long projectId;
    private FileBusinessType businessCode;
    private String relativePath;
    private String pathHash;
    private String fileName;
    private String extension;
    private String storageUuid;
    private String storageName;
    private String objectKey;
    private String minioPath;
    private String contentType;
    private Long sizeBytes;
    private Long sourceMtimeMs;
    private String quickFingerprint;
    private String contentHash;
    private ProjectFileStatus status;
    private ProjectFileUploadStatus uploadStatus;
    private Integer uploadAttempts;
    private Integer parseAttempts;
    private String detailRef;
    private String analysisVersion;
    private String module;
    private String kind;
    private String fileType;
    private String language;
    private String importance;
    private String summary;
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> keywords;
    private String lastErrorCode;
    private String lastErrorMessage;
    private java.time.LocalDateTime lastFailedAt;
    private Integer lockVersion;
}
