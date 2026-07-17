ALTER TABLE pm_project_file
    ADD COLUMN storage_name VARCHAR(255) NULL COMMENT '文件名与稳定存储标识组成的对象存储名' AFTER storage_uuid,
    ADD COLUMN minio_path VARCHAR(512) NULL COMMENT '项目根目录下的 MinIO 相对路径' AFTER object_key,
    ADD COLUMN upload_status VARCHAR(16) NOT NULL DEFAULT 'retrying' COMMENT '上传结果：retrying、success、failed' AFTER status,
    ADD COLUMN analysis_status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '详情解析状态' AFTER upload_status,
    ADD COLUMN analysis_version VARCHAR(64) NULL COMMENT '详情解析器或 Prompt 版本' AFTER analysis_status,
    ADD COLUMN detail_ref VARCHAR(512) NULL COMMENT '详情文件在项目根目录下的固定引用' AFTER analysis_version,
    ADD COLUMN analysis_module VARCHAR(128) NULL COMMENT '供 index.json 回填的模块' AFTER detail_ref,
    ADD COLUMN analysis_kind VARCHAR(64) NULL COMMENT '供 index.json 回填的文件类别' AFTER analysis_module,
    ADD COLUMN analysis_language VARCHAR(32) NULL COMMENT '供 index.json 回填的语言' AFTER analysis_kind,
    ADD COLUMN analysis_importance VARCHAR(16) NULL COMMENT '供 index.json 回填的重要程度' AFTER analysis_language,
    ADD COLUMN analysis_summary VARCHAR(1000) NULL COMMENT '供 index.json 回填的摘要' AFTER analysis_importance,
    ADD COLUMN analysis_keywords JSON NULL COMMENT '供 index.json 回填的关键词数组' AFTER analysis_summary,
    ADD COLUMN analysis_attempts INT NOT NULL DEFAULT 0 COMMENT '详情解析结果累计回传次数' AFTER analysis_keywords,
    ADD COLUMN analysis_error_code VARCHAR(64) NULL COMMENT '最后一次详情解析错误码' AFTER analysis_attempts,
    ADD COLUMN analysis_error_message VARCHAR(500) NULL COMMENT '最后一次详情解析错误摘要' AFTER analysis_error_code,
    ADD COLUMN analyzed_at DATETIME NULL COMMENT '最近一次详情解析成功时间' AFTER analysis_error_message,
    ADD KEY idx_project_file_analysis_status (project_id, analysis_status),
    ADD CONSTRAINT ck_project_file_upload_status CHECK (
        upload_status IN ('retrying', 'success', 'failed')
    ),
    ADD CONSTRAINT ck_project_file_analysis_status CHECK (
        analysis_status IN ('pending', 'processing', 'retrying', 'success', 'failed')
    ),
    ADD CONSTRAINT ck_project_file_analysis_attempts CHECK (analysis_attempts >= 0);

UPDATE pm_project_file
SET storage_name = CASE
        WHEN LENGTH(file_name) - LENGTH(SUBSTRING_INDEX(file_name, '.', -1)) - 1 > 0
            AND RIGHT(file_name, 1) <> '.'
            THEN CONCAT(
                LEFT(file_name, LENGTH(file_name) - LENGTH(SUBSTRING_INDEX(file_name, '.', -1)) - 1),
                '-',
                storage_uuid,
                '.',
                SUBSTRING_INDEX(file_name, '.', -1)
            )
        ELSE CONCAT(file_name, '-', storage_uuid)
    END,
    minio_path = CASE
        WHEN object_key IS NULL THEN NULL
        ELSE SUBSTRING_INDEX(object_key, CONCAT('/', project_id, '/'), -1)
    END,
    upload_status = CASE
        WHEN status = 'active' THEN 'success'
        WHEN status = 'upload_failed' THEN 'failed'
        ELSE 'retrying'
    END,
    analysis_status = 'pending';

UPDATE pm_project_file
SET detail_ref = CONCAT('system/file_details/', storage_name)
WHERE storage_name IS NOT NULL;

ALTER TABLE pm_project_file
    DROP INDEX uk_project_file_storage_uuid,
    MODIFY COLUMN storage_name VARCHAR(255) NOT NULL COMMENT '文件名与稳定存储标识组成的对象存储名',
    MODIFY COLUMN detail_ref VARCHAR(512) NOT NULL COMMENT '详情文件在项目根目录下的固定引用',
    ADD UNIQUE KEY uk_project_file_storage_name (project_id, business_code, storage_name),
    ADD UNIQUE KEY uk_project_file_storage_uuid (project_id, storage_uuid),
    ADD UNIQUE KEY uk_project_file_detail_ref (project_id, detail_ref);
