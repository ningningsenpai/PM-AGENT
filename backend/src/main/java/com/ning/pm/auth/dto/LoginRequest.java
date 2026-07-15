package com.ning.pm.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * LoginRequest 是用户登录请求参数。
 *
 * @author ning
 * @date 2026-06-08
 */
public record LoginRequest(
        @NotBlank(message = "邮箱不能为空")
        @Email(message = "邮箱格式不正确")
        @Size(max = 128, message = "邮箱长度不能超过 128 个字符")
        String email,

        @NotBlank(message = "密码不能为空")
        @Size(min = 1, max = 64, message = "密码长度不能超过 64 个字符")
        String password
) {
}
