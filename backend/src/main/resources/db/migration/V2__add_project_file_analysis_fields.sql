SET @parse_attempts_exists = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'pm_project_file'
      AND column_name = 'parse_attempts'
);

SET @add_parse_attempts_sql = IF(
    @parse_attempts_exists = 0,
    'ALTER TABLE pm_project_file ADD COLUMN parse_attempts INT NOT NULL DEFAULT 0 AFTER upload_attempts',
    'SELECT 1'
);

PREPARE add_parse_attempts_statement FROM @add_parse_attempts_sql;
EXECUTE add_parse_attempts_statement;
DEALLOCATE PREPARE add_parse_attempts_statement;

ALTER TABLE pm_project_file
    ADD COLUMN detail_ref VARCHAR(512) NULL AFTER parse_attempts,
    ADD COLUMN analysis_version VARCHAR(64) NULL AFTER detail_ref,
    ADD COLUMN module VARCHAR(128) NULL AFTER analysis_version,
    ADD COLUMN kind VARCHAR(64) NULL AFTER module,
    ADD COLUMN file_type VARCHAR(64) NULL AFTER kind,
    ADD COLUMN language VARCHAR(64) NULL AFTER file_type,
    ADD COLUMN importance VARCHAR(16) NULL AFTER language,
    ADD COLUMN summary TEXT NULL AFTER importance,
    ADD COLUMN keywords JSON NULL AFTER summary,
    ADD KEY idx_project_file_parse (project_id, parse_attempts),
    ADD CONSTRAINT ck_project_file_parse_attempts CHECK (parse_attempts >= 0);
