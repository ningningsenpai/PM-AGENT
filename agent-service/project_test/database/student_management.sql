-- 简易学生管理系统 MySQL 8 建表与演示数据。
-- 识别测试点：业务主键故意使用自增 ID，供系统评估枚举和规模暴露风险。

CREATE DATABASE IF NOT EXISTS student_demo DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE student_demo;

DROP TABLE IF EXISTS student;

CREATE TABLE student (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '学生业务主键',
    student_no VARCHAR(20) NOT NULL COMMENT '学号',
    name VARCHAR(30) NOT NULL COMMENT '姓名',
    gender VARCHAR(10) NOT NULL COMMENT '性别代码',
    grade VARCHAR(20) NOT NULL COMMENT '年级',
    phone VARCHAR(20) DEFAULT NULL COMMENT '联系电话',
    email VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' COMMENT '档案状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted TINYINT NOT NULL DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (id),
    UNIQUE KEY uk_student_no (student_no),
    KEY idx_student_name (name)
) ENGINE=InnoDB COMMENT='学生档案表';

INSERT INTO student (student_no, name, gender, grade, phone, email, status)
VALUES ('20260001', '林晓雨', 'FEMALE', '2026级', '13800000001', 'xiaoyu@example.test', 'ACTIVE'),
       ('20260002', '周明远', 'MALE', '2026级', '13800000002', 'mingyuan@example.test', 'ACTIVE'),
       ('20250018', '苏小满', 'FEMALE', '2025级', '13800000003', 'xiaoman@example.test', 'INACTIVE');

