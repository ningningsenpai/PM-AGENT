package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.ProjectFileUploadRequestStatus;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

@Getter
@Setter
@TableName("pm_project_file_upload_request")
public class ProjectFileUploadRequest extends BaseEntity {

    private Long ownerUserId;
    private Long projectId;
    private String requestId;
    private Integer originalTotalFiles;
    private Integer currentAttempt;
    private Integer roundTotalFiles;
    private Integer roundTotalBatches;
    private String roundManifestHash;
    private ProjectFileUploadRequestStatus status;
    private Integer succeededFiles;
    private Integer failedFiles;
    private LocalDateTime indexRebuiltAt;
    private LocalDateTime completedAt;
}
