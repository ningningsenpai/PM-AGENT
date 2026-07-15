package com.ning.pm.auth.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.auth.dto.LoginRequest;
import com.ning.pm.auth.dto.LoginResponse;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.auth.service.AuthService;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.response.R;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
@Slf4j
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;
    private final CurrentUserHolder currentUserHolder;

    /** 注册用户并返回登录态。 */
    @PostMapping("/register")
    public R<LoginResponse> register(@Valid @RequestBody RegisterRequest request) {
        log.info("开始注册用户");
        LoginResponse response = authService.register(request);
        log.info("用户注册成功 userId={}", response.user().id());
        return R.success(response);
    }

    /** 校验邮箱和密码并返回登录态。 */
    @PostMapping("/login")
    public R<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        log.info("开始登录");
        LoginResponse response = authService.login(request);
        log.info("用户登录成功 userId={}", response.user().id());
        return R.success(response);
    }

    /** 退出当前登录态。 */
    @SaCheckLogin
    @PostMapping("/logout")
    public R<Void> logout() {
        Long userId = currentUserHolder.requireUserId();
        authService.logout();
        log.info("退出登录成功 userId={}", userId);
        return R.success(null);
    }
}
