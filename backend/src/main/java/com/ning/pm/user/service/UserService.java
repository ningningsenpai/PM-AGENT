package com.ning.pm.user.service;

import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.dto.ChangePasswordRequest;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;

import java.time.LocalDateTime;

/**
 * UserService 提供用户资料与账号数据的基础业务能力。
 *
 * @author ning
 * @date 2026-06-08
 */
public interface UserService {

    User createUser(RegisterRequest request, String username, String email, String passwordHash, LocalDateTime lastLoginAt);

    User findByEmail(String email);

    UserProfileResponse getCurrentUserProfile();

    UserProfileResponse updateCurrentUserProfile(UpdateUserProfileRequest request);

    void changeCurrentUserPassword(ChangePasswordRequest request);

    void updateLastLoginAt(Long userId, LocalDateTime loginAt);
}
