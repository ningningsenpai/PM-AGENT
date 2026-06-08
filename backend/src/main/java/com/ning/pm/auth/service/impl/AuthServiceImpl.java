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
import com.ning.pm.user.service.UserService;
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
public class AuthServiceImpl implements com.ning.pm.auth.service.AuthService {

    private static final String STATUS_ENABLED = "enabled";

    private final UserService userService;
    private final UserConverter userConverter;

    public AuthServiceImpl(UserService userService, UserConverter userConverter) {
        this.userService = userService;
        this.userConverter = userConverter;
    }

    /**
     * 注册后直接建立登录态，便于第 1 阶段前端完成最小闭环。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginResponse register(RegisterRequest request) {
        String username = normalizeUsername(request.username());
        String passwordHash = BCrypt.hashpw(request.password(), BCrypt.gensalt());
        User user = userService.createUser(request, username, passwordHash);
        StpUtil.login(user.getId());
        return buildLoginResponse(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginResponse login(LoginRequest request) {
        String username = normalizeUsername(request.username());
        User user = userService.findActiveUserByUsername(username);
        if (user == null || !BCrypt.checkpw(request.password(), user.getPasswordHash())) {
            throw new BizException(ErrorCode.AUTH_LOGIN_FAILED);
        }
        if (!STATUS_ENABLED.equals(user.getStatus())) {
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
}
