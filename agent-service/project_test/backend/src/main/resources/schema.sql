DROP TABLE IF EXISTS student;

CREATE TABLE student (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_no VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(30) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    grade VARCHAR(20) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted TINYINT NOT NULL DEFAULT 0
);

CREATE INDEX idx_student_name ON student(name);

