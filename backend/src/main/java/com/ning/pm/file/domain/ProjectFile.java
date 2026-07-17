package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileAnalysisStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
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
    private Long ingestBatchId;
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
    private ProjectFileAnalysisStatus analysisStatus;
    private String analysisVersion;
    private String detailRef;
    private String analysisModule;
    private String analysisKind;
    private String analysisLanguage;
    private String analysisImportance;
    private String analysisSummary;
    private String analysisKeywords;
    private Integer analysisAttempts;
    private String analysisErrorCode;
    private String analysisErrorMessage;
    private java.time.LocalDateTime analyzedAt;
    private Boolean uploadCompletionRecorded;
    private Boolean analysisCompletionRecorded;
    private Integer uploadAttempts;
    private String lastErrorCode;
    private String lastErrorMessage;
    private java.time.LocalDateTime lastFailedAt;
    private Integer lockVersion;
}
