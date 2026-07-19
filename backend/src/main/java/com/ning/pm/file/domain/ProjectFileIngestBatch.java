package com.ning.pm.file.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import com.ning.pm.file.enums.FileIngestBatchStatus;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@TableName("pm_project_file_ingest_batch")
public class ProjectFileIngestBatch extends BaseEntity {

    private Long projectId;
    private Long uploadRequestId;
    private Integer attemptNo;
    private String clientBatchId;
    private String idempotencyKey;
    private String payloadHash;
    private Integer totalFiles;
    private Integer completedFiles;
    private Integer succeededFiles;
    private Integer failedFiles;
    private Integer analysisTotal;
    private Integer analysisCompleted;
    private Integer analysisSucceeded;
    private Integer analysisFailed;
    private FileIngestBatchStatus status;
}
