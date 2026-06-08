package com.ning.pm.auth.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.auth.dto.LoginRequest;
import com.ning.pm.auth.dto.LoginResponse;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.auth.service.AuthService;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.response.R;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * AuthController 提供用户注册、登录和登出接口。
 *
 * @author ning
 * @date 2026-06-08
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private final AuthService authService;
    private final CurrentUserHolder currentUserHolder;

    public AuthController(AuthService authService, CurrentUserHolder currentUserHolder) {
        this.authService = authService;
        this.currentUserHolder = currentUserHolder;
    }

    /** 注册新用户并返回登录态。 */
    @PostMapping("/register")
    public R<LoginResponse> register(@Valid @RequestBody RegisterRequest request) {
        log.info("收到用户注册请求 username={}", request.username());
        LoginResponse response = authService.register(request);
        log.info("用户注册成功 userId={}, username={}", response.user().id(), response.user().username());
        return R.success(response);
    }

    /** 校验账号密码并返回登录态。 */
    @PostMapping("/login")
    public R<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        log.info("收到登录请求 username={}", request.username());
        LoginResponse response = authService.login(request);
        log.info("用户登录成功 userId={}, username={}", response.user().id(), response.user().username());
        return R.success(response);
    }

    /** 退出当前登录态。 */
    @SaCheckLogin
    @PostMapping("/logout")
    public R<Void> logout() {
        Long userId = currentUserHolder.requireUserId();
        authService.logout();
        log.info("用户退出登录 userId={}", userId);
        return R.success(null);
    }
}
