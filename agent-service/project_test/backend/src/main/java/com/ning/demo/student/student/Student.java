package com.ning.demo.student.student;

import java.time.LocalDateTime;

/**
 * Student：承载学生档案的持久化数据。
 *
 * @author ning
 * @date 2026-07-11
 */
public record Student(
        Long id,
        String studentNo,
        String name,
        String gender,
        String grade,
        String phone,
        String email,
        String status,
        LocalDateTime createdAt
) {
}

