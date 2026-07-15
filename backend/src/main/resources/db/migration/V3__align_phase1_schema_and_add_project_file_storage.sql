ALTER TABLE pm_user
    DROP INDEX uk_user_username;

UPDATE pm_user
SET email = CONCAT('user-', id, '@pm-agent.local')
WHERE email IS NULL OR TRIM(email) = '';

ALTER TABLE pm_user
    MODIFY COLUMN username VARCHAR(64) NOT NULL COMMENT '用户名',
    MODIFY COLUMN email VARCHAR(128) NOT NULL COMMENT '登录邮箱',
    MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'enabled' COMMENT '账户状态',
    DROP COLUMN tenant_id,
    DROP COLUMN display_name,
    DROP COLUMN mobile,
    DROP COLUMN created_by,
    DROP COLUMN updated_by,
    DROP COLUMN deleted,
    ADD UNIQUE KEY uk_user_username (username),
    ADD UNIQUE KEY uk_user_email (email),
    ADD CONSTRAINT ck_user_status CHECK (status IN ('enabled', 'disabled'));

ALTER TABLE pm_project
    DROP INDEX idx_project_owner,
    DROP INDEX idx_project_status;

UPDATE pm_project
SET status = CASE WHEN status = 'disabled' THEN 'disabled' ELSE 'active' END;

ALTER TABLE pm_project
    CHANGE COLUMN name project_name VARCHAR(128) NOT NULL COMMENT '项目名称',
    CHANGE COLUMN owner_id owner_user_id BIGINT NOT NULL COMMENT '项目所属用户 ID',
    MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '项目状态',
    DROP COLUMN tenant_id,
    DROP COLUMN code,
    DROP COLUMN description,
    DROP COLUMN start_date,
    DROP COLUMN end_date,
    DROP COLUMN created_by,
    DROP COLUMN updated_by,
    DROP COLUMN deleted,
    ADD KEY idx_project_owner_status (owner_user_id, status),
    ADD CONSTRAINT ck_project_status CHECK (status IN ('active', 'disabled'));

CREATE TABLE pm_project_file (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    project_id BIGINT NOT NULL COMMENT '所属项目 ID',
    business_code VARCHAR(32) NOT NULL COMMENT '文件业务命名空间',
    relative_path VARCHAR(512) NOT NULL COMMENT '项目内逻辑相对路径',
    path_hash CHAR(64) NOT NULL COMMENT '规范化路径 SHA-256',
    file_name VARCHAR(255) NOT NULL COMMENT '当前文件名',
    extension VARCHAR(32) NULL COMMENT '文件扩展名',
    object_key VARCHAR(512) NULL COMMENT '稳定 MinIO 对象键',
    content_type VARCHAR(128) NOT NULL COMMENT 'MIME 类型',
    size_bytes BIGINT NOT NULL COMMENT '文件大小，单位字节',
    source_mtime_ms BIGINT NOT NULL COMMENT '源文件最后修改时间戳，单位毫秒',
    quick_fingerprint CHAR(64) NOT NULL COMMENT '路径、大小和修改时间快速指纹',
    content_hash CHAR(64) NOT NULL COMMENT '文件内容 SHA-256',
    status VARCHAR(32) NOT NULL COMMENT '文件状态',
    lock_version INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_file_path (project_id, business_code, path_hash),
    UNIQUE KEY uk_project_file_object_key (object_key),
    KEY idx_project_file_content (project_id, business_code, content_hash),
    KEY idx_project_file_status (project_id, business_code, status),
    CONSTRAINT ck_project_file_business CHECK (business_code IN ('project', 'user', 'system')),
    CONSTRAINT ck_project_file_status CHECK (
        status IN ('uploading', 'active', 'updating', 'upload_failed', 'verify_required', 'missing', 'deleting', 'delete_failed')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目逻辑文件表';

CREATE TABLE pm_project_file_upload (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    project_id BIGINT NOT NULL COMMENT '所属项目 ID',
    business_code VARCHAR(32) NOT NULL COMMENT '文件业务命名空间',
    source VARCHAR(32) NOT NULL COMMENT '上传来源',
    status VARCHAR(32) NOT NULL COMMENT '上传状态',
    idempotency_key VARCHAR(64) NOT NULL COMMENT '幂等键',
    total_files INT NOT NULL DEFAULT 1 COMMENT '文件总数',
    uploaded_files INT NOT NULL DEFAULT 0 COMMENT '已上传文件数',
    skipped_files INT NOT NULL DEFAULT 0 COMMENT '跳过文件数',
    failed_files INT NOT NULL DEFAULT 0 COMMENT '失败文件数',
    started_at DATETIME NOT NULL COMMENT '开始时间',
    completed_at DATETIME NULL COMMENT '完成时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_file_upload_idempotency (project_id, business_code, idempotency_key),
    KEY idx_file_upload_status (project_id, status, created_at),
    CONSTRAINT ck_file_upload_business CHECK (business_code IN ('project', 'user', 'system')),
    CONSTRAINT ck_file_upload_source CHECK (source IN ('frontend', 'agent', 'system')),
    CONSTRAINT ck_file_upload_status CHECK (
        status IN ('pending', 'comparing', 'uploading', 'completed', 'partial_failed', 'failed')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目文件上传批次表';

CREATE TABLE pm_project_file_upload_item (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    upload_id BIGINT NOT NULL COMMENT '上传批次 ID',
    file_id BIGINT NULL COMMENT '项目文件 ID',
    relative_path VARCHAR(512) NOT NULL COMMENT '本次处理的逻辑相对路径',
    quick_fingerprint CHAR(64) NOT NULL COMMENT '本次快速指纹',
    content_hash CHAR(64) NOT NULL COMMENT '本次内容 SHA-256',
    size_bytes BIGINT NOT NULL COMMENT '本次文件大小',
    content_type VARCHAR(128) NOT NULL COMMENT 'MIME 类型',
    source_mtime_ms BIGINT NOT NULL COMMENT '本次源文件修改时间戳',
    action VARCHAR(32) NOT NULL COMMENT '文件变更动作',
    status VARCHAR(32) NOT NULL COMMENT '处理状态',
    error_message VARCHAR(500) NULL COMMENT '失败原因摘要',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_file_upload_item_upload (upload_id, status),
    KEY idx_file_upload_item_file (file_id, created_at),
    CONSTRAINT ck_file_upload_item_action CHECK (
        action IN ('unchanged', 'create', 'metadata_update', 'path_move', 'content_overwrite', 'missing', 'delete')
    ),
    CONSTRAINT ck_file_upload_item_status CHECK (
        status IN ('pending', 'processing', 'skipped', 'success', 'failed')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目文件上传明细表';
