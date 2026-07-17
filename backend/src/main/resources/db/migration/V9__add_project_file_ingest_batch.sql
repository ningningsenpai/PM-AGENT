ALTER TABLE pm_project_file
    ADD COLUMN ingest_batch_id BIGINT NULL COMMENT '所属文件导入批次' AFTER project_id,
    ADD COLUMN upload_completion_recorded TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已计入批次上传终态' AFTER analyzed_at,
    ADD COLUMN analysis_completion_recorded TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已计入批次解析终态' AFTER upload_completion_recorded,
    ADD KEY idx_project_file_ingest_batch (ingest_batch_id, upload_status, analysis_status);

CREATE TABLE pm_project_file_ingest_batch (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    project_id BIGINT NOT NULL COMMENT '所属项目 ID',
    idempotency_key VARCHAR(64) NOT NULL COMMENT '批次创建幂等键',
    total_files INT NOT NULL COMMENT '符合上传条件的文件总数',
    completed_files INT NOT NULL DEFAULT 0 COMMENT '进入上传终态的文件数',
    succeeded_files INT NOT NULL DEFAULT 0 COMMENT '上传成功文件数',
    failed_files INT NOT NULL DEFAULT 0 COMMENT '上传最终失败文件数',
    analysis_total INT NOT NULL DEFAULT 0 COMMENT '需要详情解析的文件数',
    analysis_completed INT NOT NULL DEFAULT 0 COMMENT '进入解析终态的文件数',
    analysis_succeeded INT NOT NULL DEFAULT 0 COMMENT '详情解析成功文件数',
    analysis_failed INT NOT NULL DEFAULT 0 COMMENT '详情解析最终失败文件数',
    status VARCHAR(32) NOT NULL DEFAULT 'uploading' COMMENT '批次状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_file_ingest_batch_idempotency (project_id, idempotency_key),
    KEY idx_file_ingest_batch_project_status (project_id, status, created_at),
    CONSTRAINT ck_file_ingest_batch_status CHECK (
        status IN ('uploading', 'upload_completed', 'analyzing', 'completed')
    ),
    CONSTRAINT ck_file_ingest_batch_counts CHECK (
        total_files >= 0
        AND completed_files >= 0
        AND completed_files <= total_files
        AND succeeded_files >= 0
        AND failed_files >= 0
        AND succeeded_files + failed_files = completed_files
        AND analysis_total >= 0
        AND analysis_completed >= 0
        AND analysis_completed <= analysis_total
        AND analysis_succeeded >= 0
        AND analysis_failed >= 0
        AND analysis_succeeded + analysis_failed = analysis_completed
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目文件导入批次';
