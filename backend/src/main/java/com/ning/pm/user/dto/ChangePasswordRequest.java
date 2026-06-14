package com.ning.pm.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * ChangePasswordRequest 表示当前用户修改密码请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record ChangePasswordRequest(
        @NotBlank(message = "原密码不能为空")
        @Size(max = 64, message = "原密码长度不能超过 64 个字符")
        String oldPassword,

        @NotBlank(message = "新密码不能为空")
        @Size(min = 8, max = 64, message = "新密码长度必须在 8 到 64 个字符之间")
        String newPassword,

        @NotBlank(message = "确认密码不能为空")
        @Size(min = 8, max = 64, message = "确认密码长度必须在 8 到 64 个字符之间")
        String confirmPassword
) {
}
