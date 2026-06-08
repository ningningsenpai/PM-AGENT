INSERT INTO pm_user (id, tenant_id, username, password_hash, display_name, email, status, created_by, updated_by)
VALUES (1, 0, 'admin', '$2a$10$pmagentplaceholderpasswordhash', '宁宁', 'admin@pm-agent.local', 'enabled', 1, 1);

INSERT INTO pm_project (id, tenant_id, name, code, description, owner_id, status, start_date, end_date, created_by, updated_by)
VALUES (1, 0, 'PM-Agent 平台 MVP', 'PM-MVP', '完成登录、项目、任务和看板最小闭环，为后续 Agent 能力提供真实业务数据。', 1, 'running', '2026-06-01', '2026-07-15', 1, 1);

INSERT INTO pm_project_member (id, tenant_id, project_id, user_id, project_role, created_by, updated_by)
VALUES (1, 0, 1, 1, 'owner', 1, 1);

INSERT INTO pm_task (id, tenant_id, project_id, title, description, assignee_id, status, priority, due_date, estimated_hours, created_by, updated_by)
VALUES
    (1, 0, 1, '初始化前端工程骨架', '创建 Vite、Vue Router、Pinia、Axios 与 Naive UI 基础结构。', 1, 'done', 'p1', '2026-06-06', 4.00, 1, 1),
    (2, 0, 1, '准备 MySQL Docker 容器', '创建 deploy 目录、Docker Compose 与环境变量示例。', 1, 'developing', 'p1', '2026-06-07', 2.00, 1, 1),
    (3, 0, 1, '设计任务状态流转接口', '实现状态校验并写入任务状态日志。', 1, 'pending', 'p0', '2026-06-08', 5.00, 1, 1),
    (4, 0, 1, '联调项目列表页面', '从 Mock 数据切换到真实接口后验证项目列表。', 1, 'testing', 'p2', '2026-06-10', 3.00, 1, 1);

INSERT INTO pm_task_status_log (tenant_id, task_id, from_status, to_status, operator_id, source, reason, trace_id)
VALUES
    (0, 1, NULL, 'done', 1, 'system', '初始化演示数据', 'init'),
    (0, 2, NULL, 'developing', 1, 'system', '初始化演示数据', 'init'),
    (0, 3, NULL, 'pending', 1, 'system', '初始化演示数据', 'init'),
    (0, 4, NULL, 'testing', 1, 'system', '初始化演示数据', 'init');
