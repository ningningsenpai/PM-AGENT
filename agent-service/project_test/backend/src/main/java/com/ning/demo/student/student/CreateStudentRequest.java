package com.ning.demo.student.student;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * CreateStudentRequest：定义新增学生时允许提交的字段与校验规则。
 *
 * @author ning
 * @date 2026-07-11
 */
public record CreateStudentRequest(
        @NotBlank(message = "学号不能为空") @Size(min = 4, max = 20, message = "学号长度应为4到20个字符") String studentNo,
        @NotBlank(message = "姓名不能为空") @Size(min = 2, max = 30, message = "姓名长度应为2到30个字符") String name,
        @NotBlank(message = "性别不能为空") @Pattern(regexp = "MALE|FEMALE", message = "性别参数不合法") String gender,
        @NotBlank(message = "年级不能为空") @Size(max = 20, message = "年级不能超过20个字符") String grade,
        @Size(max = 20, message = "电话不能超过20个字符") String phone,
        @Email(message = "邮箱格式不正确") @Size(max = 100, message = "邮箱不能超过100个字符") String email
) {
}

