package com.ning.pm.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * RegisterRequest 是用户注册请求参数。
 *
 * @author ning
 * @date 2026-06-08
 */
public record RegisterRequest(
        @NotBlank(message = "用户名不能为空")
        @Size(max = 64, message = "用户名长度不能超过 64 个字符")
        String username,

        @NotBlank(message = "密码不能为空")
        @Size(min = 8, max = 64, message = "密码长度必须在 8 到 64 个字符之间")
        String password,

        @NotBlank(message = "展示名称不能为空")
        @Size(max = 64, message = "展示名称长度不能超过 64 个字符")
        String displayName,

        @Email(message = "邮箱格式不正确")
        @Size(max = 128, message = "邮箱长度不能超过 128 个字符")
        String email,

        @Size(max = 32, message = "手机号长度不能超过 32 个字符")
        String mobile
) {
}
