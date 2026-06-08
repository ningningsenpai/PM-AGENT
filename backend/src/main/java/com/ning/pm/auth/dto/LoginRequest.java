package com.ning.pm.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * LoginRequest 是用户登录请求参数。
 *
 * @author ning
 * @date 2026-06-08
 */
public record LoginRequest(
        @NotBlank(message = "用户名不能为空")
        @Size(max = 64, message = "用户名长度不能超过 64 个字符")
        String username,

        @NotBlank(message = "密码不能为空")
        @Size(min = 1, max = 64, message = "密码长度不能超过 64 个字符")
        String password
) {
}
