CREATE TABLE pm_user (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    username VARCHAR(64) NOT NULL COMMENT '登录用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    display_name VARCHAR(64) NOT NULL COMMENT '展示名称',
    email VARCHAR(128) NULL COMMENT '邮箱',
    mobile VARCHAR(32) NULL COMMENT '手机号',
    status VARCHAR(32) NOT NULL DEFAULT 'enabled' COMMENT '用户状态',
    last_login_at DATETIME NULL COMMENT '最近登录时间',
    created_by BIGINT NULL COMMENT '创建人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT NULL COMMENT '更新人 ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_username (tenant_id, username, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

CREATE TABLE pm_project (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    name VARCHAR(128) NOT NULL COMMENT '项目名称',
    code VARCHAR(64) NULL COMMENT '项目编码',
    description TEXT NULL COMMENT '项目说明',
    owner_id BIGINT NOT NULL COMMENT '项目负责人',
    status VARCHAR(32) NOT NULL DEFAULT 'not_started' COMMENT '项目状态',
    start_date DATE NULL COMMENT '计划开始日期',
    end_date DATE NULL COMMENT '计划结束日期',
    created_by BIGINT NULL COMMENT '创建人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT NULL COMMENT '更新人 ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    KEY idx_project_owner (tenant_id, owner_id, deleted),
    KEY idx_project_status (tenant_id, status, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目表';

CREATE TABLE pm_project_member (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    project_id BIGINT NOT NULL COMMENT '项目 ID',
    user_id BIGINT NOT NULL COMMENT '用户 ID',
    project_role VARCHAR(32) NOT NULL COMMENT '项目内角色',
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    created_by BIGINT NULL COMMENT '创建人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT NULL COMMENT '更新人 ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_member (project_id, user_id, deleted),
    KEY idx_project_member_user (tenant_id, user_id, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目成员表';

CREATE TABLE pm_task (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    project_id BIGINT NOT NULL COMMENT '所属项目',
    requirement_id BIGINT NULL COMMENT '关联需求',
    iteration_id BIGINT NULL COMMENT '所属迭代',
    title VARCHAR(255) NOT NULL COMMENT '任务标题',
    description TEXT NULL COMMENT '任务说明',
    assignee_id BIGINT NULL COMMENT '负责人',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    priority VARCHAR(32) NOT NULL DEFAULT 'p2' COMMENT '优先级',
    due_date DATE NULL COMMENT '截止日期',
    estimated_hours DECIMAL(8,2) NULL COMMENT '预估工时',
    actual_hours DECIMAL(8,2) NULL COMMENT '实际工时',
    created_by BIGINT NULL COMMENT '创建人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT NULL COMMENT '更新人 ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    KEY idx_task_project_status (tenant_id, project_id, status, deleted),
    KEY idx_task_assignee (tenant_id, assignee_id, status, deleted),
    KEY idx_task_due_date (tenant_id, due_date, deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务表';

CREATE TABLE pm_task_status_log (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '多租户预留字段',
    task_id BIGINT NOT NULL COMMENT '任务 ID',
    from_status VARCHAR(32) NULL COMMENT '原状态',
    to_status VARCHAR(32) NOT NULL COMMENT '新状态',
    operator_id BIGINT NULL COMMENT '操作人',
    source VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '变更来源',
    reason VARCHAR(255) NULL COMMENT '变更原因',
    trace_id VARCHAR(64) NULL COMMENT '链路追踪 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_task_status_log_task (tenant_id, task_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务状态日志表';
