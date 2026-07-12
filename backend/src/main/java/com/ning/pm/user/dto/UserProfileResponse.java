package com.ning.pm.user.dto;

import com.ning.pm.user.domain.UserStatus;

import java.time.LocalDateTime;

/**
 * UserProfileResponse 是对外返回的安全用户资料。
 *
 * @author ning
 * @date 2026-06-08
 */
public record UserProfileResponse(
        Long id,
        String username,
        String email,
        UserStatus status,
        LocalDateTime lastLoginAt
) {
}
