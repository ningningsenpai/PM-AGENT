package com.ning.pm.auth.dto;

import com.ning.pm.user.dto.UserProfileResponse;

/**
 * LoginResponse 是登录成功后返回的登录态与用户资料。
 *
 * @author ning
 * @date 2026-06-08
 */
public record LoginResponse(
        String tokenName,
        String tokenValue,
        UserProfileResponse user
) {
}
