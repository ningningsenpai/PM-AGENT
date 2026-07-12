package com.ning.pm.user.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.response.R;
import com.ning.pm.user.dto.ChangePasswordRequest;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * UserController 提供当前账户资料查询接口。
 *
 * @author ning
 * @date 2026-06-08
 */
@RestController
@RequestMapping("/api/v1/users")
@Slf4j
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final CurrentUserHolder currentUserHolder;

    /** 查询当前登录用户的账户资料。 */
    @SaCheckLogin
    @GetMapping("/me")
    public R<UserProfileResponse> me() {
        Long userId = currentUserHolder.requireUserId();
        log.info("开始查询当前账户信息 userId={}", userId);
        UserProfileResponse response = userService.getCurrentUserProfile();
        log.info("查询当前账户信息成功 userId={}", userId);
        return R.success(response);
    }

    /** 修改当前登录用户的账户资料。 */
    @SaCheckLogin
    @PutMapping("/me")
    public R<UserProfileResponse> updateMe(@Valid @RequestBody UpdateUserProfileRequest request) {
        Long userId = currentUserHolder.requireUserId();
        log.info("开始修改当前账户信息 userId={}", userId);
        UserProfileResponse response = userService.updateCurrentUserProfile(request);
        log.info("修改当前账户信息成功 userId={}", userId);
        return R.success(response);
    }

    /** 修改当前登录用户的密码。 */
    @SaCheckLogin
    @PutMapping("/me/password")
    public R<Void> changePassword(@Valid @RequestBody ChangePasswordRequest request) {
        Long userId = currentUserHolder.requireUserId();
        log.info("开始修改当前账户密码 userId={}", userId);
        userService.changeCurrentUserPassword(request);
        log.info("修改当前账户密码成功 userId={}", userId);
        return R.success(null);
    }
}
