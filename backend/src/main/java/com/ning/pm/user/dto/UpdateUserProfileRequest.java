package com.ning.pm.user.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * UpdateUserProfileRequest 表示当前用户资料修改请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record UpdateUserProfileRequest(
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
