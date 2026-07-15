package com.ning.demo.student.common;

/**
 * StudentNotFoundException：表示指定学生档案不存在。
 *
 * @author ning
 * @date 2026-07-11
 */
public class StudentNotFoundException extends RuntimeException {

    public StudentNotFoundException() {
        super("学生不存在");
    }
}

