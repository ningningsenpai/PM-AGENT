ALTER TABLE pm_project
    DROP CHECK ck_project_status,
    ADD CONSTRAINT ck_project_status CHECK (
        status IN ('initializing', 'active', 'init_failed', 'disabled', 'deleting', 'delete_failed')
    );
