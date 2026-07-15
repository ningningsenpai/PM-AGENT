package com.ning.pm.auth.service.impl;

import cn.dev33.satoken.stp.SaTokenInfo;
import cn.dev33.satoken.stp.StpUtil;
import cn.hutool.crypto.digest.BCrypt;
import com.ning.pm.auth.dto.LoginRequest;
import com.ning.pm.auth.dto.LoginResponse;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.domain.UserStatus;
import com.ning.pm.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Locale;

/**
 * AuthServiceImpl 实现用户注册、登录和登出流程。
 *
 * @author ning
 * @date 2026-06-08
 */
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements com.ning.pm.auth.service.AuthService {

    private final UserService userService;
    private final UserConverter userConverter;

    /** 注册用户，并在成功后直接建立登录态。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginResponse register(RegisterRequest request) {
        String username = normalizeUsername(request.username());
        String email = normalizeEmail(request.email());
        String passwordHash = BCrypt.hashpw(request.password(), BCrypt.gensalt());
        LocalDateTime lastLoginAt = LocalDateTime.now();
        User user = userService.createUser(request, username, email, passwordHash, lastLoginAt);
        StpUtil.login(user.getId());
        return buildLoginResponse(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginResponse login(LoginRequest request) {
        String email = normalizeEmail(request.email());
        User user = userService.findByEmail(email);
        if (user == null || !BCrypt.checkpw(request.password(), user.getPasswordHash())) {
            throw new BizException(ErrorCode.AUTH_LOGIN_FAILED);
        }
        if (user.getStatus() != UserStatus.ENABLED) {
            throw new BizException(ErrorCode.USER_DISABLED);
        }

        StpUtil.login(user.getId());
        user.setLastLoginAt(LocalDateTime.now());
        userService.updateLastLoginAt(user.getId(), user.getLastLoginAt());
        return buildLoginResponse(user);
    }

    @Override
    public void logout() {
        StpUtil.logout();
    }

    private LoginResponse buildLoginResponse(User user) {
        SaTokenInfo tokenInfo = StpUtil.getTokenInfo();
        return new LoginResponse(tokenInfo.tokenName, tokenInfo.tokenValue, userConverter.toProfileResponse(user));
    }

    private String normalizeUsername(String username) {
        return username.trim().toLowerCase(Locale.ROOT);
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}
