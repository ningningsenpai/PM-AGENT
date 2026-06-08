package com.ning.pm.auth.service;

import com.ning.pm.auth.dto.LoginRequest;
import com.ning.pm.auth.dto.LoginResponse;
import com.ning.pm.auth.dto.RegisterRequest;

/**
 * AuthService 提供注册、登录和登出的认证业务能力。
 *
 * @author ning
 * @date 2026-06-08
 */
public interface AuthService {

    LoginResponse register(RegisterRequest request);

    LoginResponse login(LoginRequest request);

    void logout();
}
