package com.ning.pm.user.dto;

import java.time.LocalDateTime;

/**
 * UserProfileResponse 是对外返回的安全用户资料。
 *
 * @author ning
 * @date 2026-06-08
 */
public record UserProfileResponse(
        Long id,
        Long tenantId,
        String username,
        String displayName,
        String email,
        String mobile,
        String status,
        LocalDateTime lastLoginAt
) {
}
