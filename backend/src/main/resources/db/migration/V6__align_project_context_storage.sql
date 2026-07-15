ALTER TABLE pm_project_file
    ADD COLUMN storage_uuid CHAR(16) NULL COMMENT '对象名中的稳定随机标识' AFTER extension,
    ADD COLUMN upload_attempts INT NOT NULL DEFAULT 0 COMMENT '当前累计上传次数' AFTER status,
    ADD COLUMN last_error_code VARCHAR(64) NULL COMMENT '最后一次错误码' AFTER upload_attempts,
    ADD COLUMN last_error_message VARCHAR(500) NULL COMMENT '脱敏后的中文错误摘要' AFTER last_error_code,
    ADD COLUMN last_failed_at DATETIME NULL COMMENT '最后失败时间' AFTER last_error_message;

UPDATE pm_project_file
SET storage_uuid = SUBSTRING(REPLACE(UUID(), '-', ''), 1, 16)
WHERE storage_uuid IS NULL;

ALTER TABLE pm_project_file
    MODIFY COLUMN storage_uuid CHAR(16) NOT NULL COMMENT '对象名中的稳定随机标识',
    ADD UNIQUE KEY uk_project_file_storage_uuid (project_id, business_code, storage_uuid),
    ADD CONSTRAINT ck_project_file_upload_attempts CHECK (upload_attempts >= 0);

ALTER TABLE pm_project
    DROP CHECK ck_project_status,
    ADD CONSTRAINT ck_project_status CHECK (
        status IN ('active', 'disabled', 'deleting', 'delete_failed')
    );
