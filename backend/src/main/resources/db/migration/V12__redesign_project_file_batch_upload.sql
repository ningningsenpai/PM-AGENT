CREATE TABLE pm_project_file_upload_request (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    owner_user_id BIGINT NOT NULL COMMENT '项目所属用户ID',
    project_id BIGINT NOT NULL COMMENT '项目ID',
    request_id VARCHAR(64) NOT NULL COMMENT '前端一次完整上传请求的稳定ID',
    original_total_files INT NOT NULL COMMENT '首次筛选后的文件总数',
    current_attempt TINYINT NOT NULL COMMENT '当前上传轮次，范围1到3',
    round_total_files INT NOT NULL COMMENT '当前轮需要上传的文件数',
    round_total_batches INT NOT NULL COMMENT '当前轮预注册的物理批次数',
    round_manifest_hash CHAR(64) NOT NULL COMMENT '当前轮批次摘要哈希',
    status VARCHAR(32) NOT NULL DEFAULT 'uploading' COMMENT '请求级上传状态',
    succeeded_files INT NOT NULL DEFAULT 0 COMMENT '已成功上传文件数',
    failed_files INT NOT NULL DEFAULT 0 COMMENT '最终失败文件数，仅终态有意义',
    index_rebuilt_at DATETIME NULL COMMENT '终态后同步重建index.json的完成时间',
    completed_at DATETIME NULL COMMENT '请求进入最终态的时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_file_upload_request (project_id, request_id),
    KEY idx_file_upload_request_project_status (project_id, status, created_at),
    CONSTRAINT ck_file_upload_request_status CHECK (
        status IN ('uploading', 'awaiting_retry', 'completed', 'completed_with_failures')
    ),
    CONSTRAINT ck_file_upload_request_attempt CHECK (current_attempt BETWEEN 1 AND 3),
    CONSTRAINT ck_file_upload_request_counts CHECK (
        original_total_files > 0
        AND round_total_files > 0
        AND round_total_batches > 0
        AND succeeded_files >= 0
        AND succeeded_files <= original_total_files
        AND failed_files >= 0
        AND failed_files <= original_total_files
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目文件请求级批次上传根记录';

ALTER TABLE pm_project_file_ingest_batch
    ADD COLUMN upload_request_id BIGINT NULL COMMENT '请求级上传根记录ID' AFTER project_id,
    ADD COLUMN attempt_no TINYINT NULL COMMENT '所属上传轮次' AFTER upload_request_id,
    ADD COLUMN client_batch_id VARCHAR(64) NULL COMMENT '前端批次ID' AFTER attempt_no,
    MODIFY COLUMN idempotency_key VARCHAR(64) NULL COMMENT '批次首次提交时写入的幂等键',
    ADD COLUMN payload_hash CHAR(64) NULL COMMENT '批次文件描述与内容指纹的稳定摘要' AFTER idempotency_key,
    MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'waiting' COMMENT '物理批次状态',
    ADD UNIQUE KEY uk_file_ingest_request_batch (upload_request_id, attempt_no, client_batch_id),
    ADD KEY idx_file_ingest_request_round_status (upload_request_id, attempt_no, status),
    DROP CHECK ck_file_ingest_batch_status,
    ADD CONSTRAINT ck_file_ingest_batch_status CHECK (
        status IN (
            'waiting', 'processing', 'completed',
            'uploading', 'upload_completed', 'analyzing'
        )
    );

ALTER TABLE pm_project_file
    ADD COLUMN upload_request_id BIGINT NULL COMMENT '请求级上传根记录ID' AFTER project_id,
    ADD COLUMN client_file_id VARCHAR(128) NULL COMMENT '前端稳定文件ID，重试时保持不变' AFTER upload_request_id,
    ADD COLUMN last_upload_attempt TINYINT NOT NULL DEFAULT 0 COMMENT '最近一次实际上传轮次' AFTER analysis_completion_recorded,
    ADD COLUMN last_upload_batch_id BIGINT NULL COMMENT '最近一次实际上传的物理批次ID' AFTER last_upload_attempt,
    MODIFY COLUMN storage_uuid CHAR(16) NULL COMMENT '上传成功后写入的稳定存储标识',
    MODIFY COLUMN storage_name VARCHAR(255) NULL COMMENT '上传成功后写入的对象存储名',
    MODIFY COLUMN object_key VARCHAR(512) NULL COMMENT '上传成功后写入的MinIO对象键',
    MODIFY COLUMN minio_path VARCHAR(512) NULL COMMENT '上传成功后写入的MinIO相对路径',
    MODIFY COLUMN detail_ref VARCHAR(512) NULL COMMENT '上传成功后写入的详情文件引用',
    MODIFY COLUMN upload_status VARCHAR(16) NOT NULL DEFAULT 'not_uploaded' COMMENT '文件上传事实状态',
    ADD UNIQUE KEY uk_project_file_upload_client (upload_request_id, client_file_id),
    ADD KEY idx_project_file_upload_request_status (upload_request_id, upload_status),
    DROP CHECK ck_project_file_upload_status,
    ADD CONSTRAINT ck_project_file_upload_status CHECK (
        upload_status IN ('not_uploaded', 'success', 'retrying', 'failed')
    );
