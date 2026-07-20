CREATE TABLE pm_user (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    email VARCHAR(128) NOT NULL COMMENT '登录邮箱',
    status VARCHAR(32) NOT NULL DEFAULT 'enabled' COMMENT '账户状态',
    last_login_at DATETIME NULL COMMENT '最近登录时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_username (username),
    UNIQUE KEY uk_user_email (email),
    CONSTRAINT ck_user_status CHECK (status IN ('enabled', 'disabled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

CREATE TABLE pm_project (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    owner_user_id BIGINT NOT NULL COMMENT '项目所属用户 ID',
    project_name VARCHAR(128) NOT NULL COMMENT '项目名称',
    status VARCHAR(32) NOT NULL DEFAULT 'initializing' COMMENT '项目状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_project_owner_status (owner_user_id, status),
    CONSTRAINT ck_project_status CHECK (
        status IN ('initializing', 'active', 'init_failed')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目表';

CREATE TABLE pm_project_file (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    project_id BIGINT NOT NULL COMMENT '所属项目 ID',
    business_code VARCHAR(32) NOT NULL COMMENT '文件业务命名空间',
    relative_path VARCHAR(512) NOT NULL COMMENT '项目内逻辑相对路径',
    path_hash CHAR(64) NOT NULL COMMENT '规范化路径 SHA-256',
    file_name VARCHAR(255) NOT NULL COMMENT '当前文件名',
    extension VARCHAR(32) NULL COMMENT '文件扩展名',
    storage_uuid CHAR(16) NOT NULL COMMENT '对象名中的稳定随机标识',
    storage_name VARCHAR(255) NOT NULL COMMENT '文件名与稳定标识组成的对象存储名',
    object_key VARCHAR(512) NOT NULL COMMENT '稳定 MinIO 对象键',
    minio_path VARCHAR(512) NOT NULL COMMENT '项目根目录下的 MinIO 相对路径',
    content_type VARCHAR(128) NOT NULL COMMENT 'MIME 类型',
    size_bytes BIGINT NOT NULL COMMENT '文件大小，单位字节',
    source_mtime_ms BIGINT NOT NULL COMMENT '源文件最后修改时间戳，单位毫秒',
    quick_fingerprint CHAR(64) NOT NULL COMMENT '路径、大小和修改时间快速指纹',
    content_hash CHAR(64) NOT NULL COMMENT '文件内容 SHA-256',
    status VARCHAR(32) NOT NULL COMMENT '文件生命周期状态',
    upload_status VARCHAR(16) NOT NULL DEFAULT 'not_uploaded' COMMENT '文件上传事实状态',
    upload_attempts INT NOT NULL DEFAULT 0 COMMENT '累计上传次数',
    last_error_code VARCHAR(64) NULL COMMENT '最后一次上传错误码',
    last_error_message VARCHAR(500) NULL COMMENT '最后一次上传错误摘要',
    last_failed_at DATETIME NULL COMMENT '最后一次上传失败时间',
    lock_version INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_file_path (project_id, business_code, path_hash),
    UNIQUE KEY uk_project_file_object_key (object_key),
    UNIQUE KEY uk_project_file_storage_name (project_id, business_code, storage_name),
    UNIQUE KEY uk_project_file_storage_uuid (project_id, storage_uuid),
    KEY idx_project_file_content (project_id, business_code, content_hash),
    KEY idx_project_file_status (project_id, business_code, status),
    CONSTRAINT ck_project_file_business CHECK (
        business_code IN ('project', 'user', 'system')
    ),
    CONSTRAINT ck_project_file_status CHECK (
        status IN (
            'uploading', 'active', 'updating', 'upload_failed',
            'verify_required', 'missing', 'deleting', 'delete_failed'
        )
    ),
    CONSTRAINT ck_project_file_upload_status CHECK (
        upload_status IN ('not_uploaded', 'success', 'retrying', 'failed')
    ),
    CONSTRAINT ck_project_file_upload_attempts CHECK (upload_attempts >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目逻辑文件表';
