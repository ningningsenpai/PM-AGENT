package com.ning.demo.student.student;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 学生档案编辑请求；学号和创建时间不允许通过编辑接口修改。 */
public record UpdateStudentRequest(
        @NotBlank @Size(min = 2, max = 30) String name,
        @NotBlank String gender,
        @NotBlank @Size(max = 20) String grade,
        @Size(max = 20) String phone,
        @Email @Size(max = 100) String email,
        @NotBlank String status
) {
}

